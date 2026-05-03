"""
OpenHands - AI Agent Runner
Deep reference to OpenClaw's embedded agent architecture
"""

import asyncio
import logging
import uuid
import json
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

from ..config import AgentConfig
from ..adapters import ModelAdapter, get_adapter_class
from ...tools import file_tools, terminal_tools, memory_tools
from ..tools.registry import ToolRegistry, tool_registry
from ..tools.policy import ToolPolicyManager
from ..memory.store import MemoryStore
from ...skills import SkillManager, skill_manager
from ...skills.nudge_engine import NudgeEngine, NudgeConfig
from ..types import Message, MessageRole, SessionState, SessionStatus, ToolCall

logger = logging.getLogger(__name__)


MEMORY_GUIDANCE = """You have access to a memory system. Use it to:
- Remember important context from previous conversations
- Store user preferences and patterns
- Learn from past interactions to improve future responses

When the user asks about something you should remember, use the memory tools."""


@dataclass
class IterationBudget:
    """Iteration budget for agent runs"""
    max_total: int
    consumed: int = 0
    
    @property
    def remaining(self) -> int:
        return max(0, self.max_total - self.consumed)
    
    def consume(self):
        self.consumed += 1


@dataclass
class EmbeddedAgentRunMeta:
    """Metadata for an agent run"""
    run_id: str
    start_time: Any
    end_time: Optional[Any] = None
    iteration_count: int = 0
    tool_call_count: int = 0
    token_count: int = 0
    error_count: int = 0
    success: bool = True


@dataclass
class EmbeddedAgentRunResult:
    """Result of an agent run"""
    meta: EmbeddedAgentRunMeta
    success: bool = True
    error: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    tool_results: List[Any] = field(default_factory=list)


DEFAULT_SYSTEM_PROMPT = """You are OpenHands, a powerful AI assistant with access to tools.

## Your Capabilities
You have access to tools that let you:
- Execute terminal commands (terminal_run)
- Read and write files (read_file, write_file, list_dir)
- Store and search memories (memory_add, memory_search, memory_list)

## Tool Usage Guidelines
- **When the user asks you to run a command, execute it using terminal_run**
- **When the user asks to read a file or see directory contents, use the appropriate file tool**
- **Use tools proactively to help the user efficiently**

## Important Rules
1. If the user asks you to do something that requires a tool, use that tool
2. Execute commands exactly as requested
3. Report the results clearly to the user
4. Do not ask for confirmation for routine operations

""" + MEMORY_GUIDANCE + """

Start by introducing yourself and asking what the user would like to do."""


class EmbeddedAgent:
    """
    Embedded Agent - Core runtime
    Deep reference to OpenClaw's embedded agent
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig.load()
        self.agent_id = self.config.agent_id or f"openhands-{uuid.uuid4().hex[:8]}"

        self._adapter: Optional[ModelAdapter] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._policy_manager: ToolPolicyManager = ToolPolicyManager()
        self._memory: Optional[MemoryStore] = None
        self._sessions: Dict[str, SessionState] = {}
        self._active_runs: Dict[str, EmbeddedAgentRunMeta] = {}
        self._skill_manager: Optional[SkillManager] = None
        self._initialized = False

    async def initialize(self):
        """Initialize the agent"""
        if self._initialized:
            return

        logger.info("Initializing OpenHands Agent...")

        adapter_class = get_adapter_class(self.config.model.provider)
        if not adapter_class:
            raise ValueError(f"Unknown adapter: {self.config.model.provider}")

        self._adapter = adapter_class(self.config.model)
        await self._adapter.initialize()

        self._tool_registry = tool_registry()
        await self._load_core_tools()

        self._skill_manager = skill_manager()

        self._initialized = True
        logger.info(f"OpenHands Agent initialized: {self.agent_id}")

    async def _load_core_tools(self):
        """Load core toolsets"""
        from ...tools import file_tools, terminal_tools, memory_tools

        file_tools.register_tools(self._tool_registry)
        terminal_tools.register_tools(self._tool_registry)
        memory_tools.register_tools(self._tool_registry, self._memory)

    async def create_session(
        self,
        tool_profile: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new session"""
        session_id = str(uuid.uuid4())

        state = SessionState(
            session_id=session_id,
            messages=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            current_tool_profile=tool_profile,
            metadata=metadata or {},
        )

        self._sessions[session_id] = state
        logger.info(f"Created session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get a session by ID"""
        return self._sessions.get(session_id)

    async def queue_message(self, session_id: str, content: str):
        """Queue a message for processing"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        msg = Message(role=MessageRole.USER, content=content)
        session.messages.append(msg)

    def _to_adapter_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        """Convert internal messages to adapter format"""
        result = []
        for msg in messages:
            role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            result.append({"role": role, "content": content})
        return result

    def _from_adapter_response(self, response) -> Message:
        """Convert adapter response to internal message"""
        if hasattr(response, 'content'):
            return Message(role=MessageRole.ASSISTANT, content=response.content or "")
        return Message(role=MessageRole.ASSISTANT, content=str(response))

    async def run(
        self,
        session_id: str,
        max_iterations: Optional[int] = None,
        tool_profile: Optional[str] = None,
        system_prompt_override: Optional[str] = None,
    ) -> EmbeddedAgentRunResult:
        """Main agent run"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.status == SessionStatus.RUNNING:
            raise RuntimeError(f"Session already running: {session_id}")

        run_id = str(uuid.uuid4())
        run_meta = EmbeddedAgentRunMeta(
            run_id=run_id,
            start_time=datetime.now(),
        )
        self._active_runs[run_id] = run_meta
        session.status = SessionStatus.RUNNING

        max_iter = max_iterations or self.config.max_iterations or 30
        budget = IterationBudget(max_total=max_iter)
        tool_results: List[Any] = []

        try:
            result = await self._agent_loop(
                session=session,
                budget=budget,
                run_meta=run_meta,
                tool_profile=tool_profile,
                system_prompt_override=system_prompt_override,
                tool_results=tool_results,
            )
            result.meta = run_meta
            return result

        except Exception as e:
            logger.exception(f"Agent run failed: {run_id}")
            run_meta.success = False
            run_meta.error_count += 1
            return EmbeddedAgentRunResult(
                meta=run_meta,
                success=False,
                error=str(e),
                messages=session.messages,
            )
        finally:
            session.status = SessionStatus.COMPLETED
            session.updated_at = datetime.now()
            if run_id in self._active_runs:
                del self._active_runs[run_id]

    async def run_stream(
        self,
        session_id: str,
        max_iterations: Optional[int] = None,
        tool_profile: Optional[str] = None,
        system_prompt_override: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式Agent运行"""
        session = self.get_session(session_id)
        if not session:
            yield {"type": "error", "content": f"Session not found: {session_id}"}
            return

        if session.status == SessionStatus.RUNNING:
            yield {"type": "error", "content": f"Session already running: {session_id}"}
            return

        run_id = str(uuid.uuid4())
        run_meta = EmbeddedAgentRunMeta(
            run_id=run_id,
            start_time=datetime.now(),
        )
        self._active_runs[run_id] = run_meta
        session.status = SessionStatus.RUNNING

        max_iter = max_iterations or self.config.max_iterations or 30
        budget = IterationBudget(max_total=max_iter)
        tool_results: List[Any] = []

        try:
            async for event in self._agent_loop_stream(
                session=session,
                budget=budget,
                run_meta=run_meta,
                tool_profile=tool_profile,
                system_prompt_override=system_prompt_override,
                tool_results=tool_results,
            ):
                yield event

        except Exception as e:
            logger.exception(f"Agent stream run failed: {run_id}")
            yield {"type": "error", "content": str(e)}
        finally:
            session.status = SessionStatus.COMPLETED
            session.updated_at = datetime.now()
            if run_id in self._active_runs:
                del self._active_runs[run_id]

    async def _agent_loop_stream(
        self,
        session: SessionState,
        budget: IterationBudget,
        run_meta: EmbeddedAgentRunMeta,
        tool_profile: Optional[str],
        system_prompt_override: Optional[str],
        tool_results: List[Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """核心Agent循环流式版本"""
        profile = tool_profile or session.current_tool_profile or "full"
        system_prompt = system_prompt_override or self.config.system_prompt or DEFAULT_SYSTEM_PROMPT

        while budget.remaining > 0:
            budget.consume()
            run_meta.iteration_count += 1

            yield {
                "type": "thinking",
                "content": f"🧠 思考中 (迭代 {run_meta.iteration_count})..."
            }

            adapter_messages = self._to_adapter_messages(session.messages)
            tool_defs = self._get_available_tools(profile)

            if hasattr(self._adapter, 'chat_stream') and callable(self._adapter.chat_stream):
                response_text = ""
                pending_tool_calls = []
                
                async for chunk in self._adapter.chat_stream(
                    messages=adapter_messages,
                    tools=tool_defs,
                    system_prompt=system_prompt,
                ):
                    if chunk.content:
                        response_text += chunk.content
                        yield {
                            "type": "delta",
                            "content": chunk.content
                        }
                    
                    if chunk.tool_calls and len(chunk.tool_calls) > 0:
                        pending_tool_calls.extend(chunk.tool_calls)
                
                if response_text:
                    assistant_msg = Message(
                        role=MessageRole.ASSISTANT,
                        content=response_text,
                    )
                    session.messages.append(assistant_msg)
                
                if pending_tool_calls:
                    for tc in pending_tool_calls:
                        yield {
                            "type": "tool_call",
                            "tool": tc.name,
                            "arguments": tc.arguments
                        }
                        
                        run_meta.tool_call_count += 1
                        
                        actual_tc = ToolCall(
                            id=tc.id,
                            name=tc.name,
                            arguments=tc.arguments
                        )
                        
                        logger.info(f"执行工具: {tc.name}")
                        result = await self._tool_registry.execute_tool_call(actual_tc)
                        tool_results.append(result)
                        
                        yield {
                            "type": "tool_result",
                            "tool": tc.name,
                            "result": result.content[:800] if len(result.content) > 800 else result.content,
                            "is_error": result.is_error
                        }
                        
                        msg = Message(
                            role=MessageRole.TOOL,
                            content=result.content,
                            tool_call_id=tc.id,
                        )
                        session.messages.append(msg)
                
                else:
                    if response_text:
                        yield {
                            "type": "final",
                            "content": response_text
                        }
                    else:
                        yield {
                            "type": "final",
                            "content": "任务已完成"
                        }
                    return
            else:
                response = await self._adapter.chat(
                    messages=adapter_messages,
                    tools=tool_defs,
                    system_prompt=system_prompt,
                )

                if response.content:
                    yield {
                        "type": "delta",
                        "content": response.content
                    }

                assistant_msg = self._from_adapter_response(response)
                session.messages.append(assistant_msg)

                if response.tool_calls:
                    for tc in response.tool_calls:
                        yield {
                            "type": "tool_call",
                            "tool": tc.name,
                            "arguments": tc.arguments
                        }

                        result = await self._execute_single_tool(tc, budget, run_meta, profile)
                        tool_results.append(result)
                        
                        yield {
                            "type": "tool_result",
                            "tool": tc.name,
                            "result": result.content[:800] if len(result.content) > 800 else result.content,
                            "is_error": result.is_error
                        }

                        msg = Message(
                            role=MessageRole.TOOL,
                            content=result.content,
                            tool_call_id=tc.id,
                        )
                        session.messages.append(msg)
                else:
                    yield {
                        "type": "final",
                        "content": response.content or "处理完成"
                    }
                    return

        yield {
            "type": "final",
            "content": "达到最大迭代次数"
        }

    async def _agent_loop(
        self,
        session: SessionState,
        budget: IterationBudget,
        run_meta: EmbeddedAgentRunMeta,
        tool_profile: Optional[str],
        system_prompt_override: Optional[str],
        tool_results: List[Any],
    ):
        """核心Agent循环"""
        profile = tool_profile or session.current_tool_profile or "full"
        system_prompt = system_prompt_override or self.config.system_prompt or DEFAULT_SYSTEM_PROMPT

        while budget.remaining > 0:
            budget.consume()
            run_meta.iteration_count += 1

            adapter_messages = self._to_adapter_messages(session.messages)
            tool_defs = self._get_available_tools(profile)

            response = await self._adapter.chat(
                messages=adapter_messages,
                tools=tool_defs,
                system_prompt=system_prompt,
            )

            assistant_msg = self._from_adapter_response(response)
            session.messages.append(assistant_msg)

            if response.tool_calls:
                for tc in response.tool_calls:
                    run_meta.tool_call_count += 1
                    result = await self._execute_single_tool(tc, budget, run_meta, profile)
                    tool_results.append(result)

                    msg = Message(
                        role=MessageRole.TOOL,
                        content=result.content,
                        tool_call_id=tc.id,
                    )
                    session.messages.append(msg)
            else:
                return EmbeddedAgentRunResult(
                    meta=run_meta,
                    success=True,
                    messages=session.messages,
                    tool_results=tool_results,
                )

        return EmbeddedAgentRunResult(
            meta=run_meta,
            success=False,
            error="Max iterations reached",
            messages=session.messages,
            tool_results=tool_results,
        )

    async def _execute_single_tool(
        self,
        tool_call: Any,
        budget: IterationBudget,
        run_meta: EmbeddedAgentRunMeta,
        profile: str,
    ) -> Any:
        """执行单个工具调用"""
        logger.info(f"Executing tool: {tool_call.name}")
        run_meta.tool_call_count += 1
        
        try:
            tc = ToolCall(
                id=tool_call.id,
                name=tool_call.name,
                arguments=tool_call.arguments,
            )
            result = await self._tool_registry.execute_tool_call(tc)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            from ..types import ToolResult
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: {str(e)}",
                is_error=True,
            )

    def _get_available_tools(self, profile: str) -> List[Dict[str, Any]]:
        """Get filtered tools based on policy"""
        all_defs = self._tool_registry.get_definitions()
        all_names = [d["name"] for d in all_defs]
        allowed_names = self._policy_manager.filter_tools(all_names, profile)

        return [d for d in all_defs if d["name"] in allowed_names]
