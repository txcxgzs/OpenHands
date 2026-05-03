"""
OpenHands - AI Agent Runner
OpenClaw风格的身份验证和工作区引导
"""

import asyncio
import logging
import uuid
import os
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

from ..config import AgentConfig
from ..adapters import ModelAdapter, get_adapter_class
from ...tools import file_tools, terminal_tools, memory_tools
from ..tools.registry import ToolRegistry, tool_registry
from ..tools.policy import ToolPolicyManager
from ..memory.store import MemoryStore
from ..types import Message, MessageRole, SessionState, SessionStatus, ToolCall

logger = logging.getLogger(__name__)


@dataclass
class IterationBudget:
    max_total: int
    consumed: int = 0
    
    @property
    def remaining(self) -> int:
        return max(0, self.max_total - self.consumed)
    
    def consume(self):
        self.consumed += 1


@dataclass
class EmbeddedAgentRunMeta:
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
    meta: EmbeddedAgentRunMeta
    success: bool = True
    error: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    tool_results: List[Any] = field(default_factory=list)


# 工作区文件路径
WORKSPACE_DIR = "/workspace/openhands-workspace"
BOOTSTRAP_FILE = os.path.join(WORKSPACE_DIR, "BOOTSTRAP.md")
USER_FILE = os.path.join(WORKSPACE_DIR, "user.md")
IDENTITY_FILE = os.path.join(WORKSPACE_DIR, "identity.md")


def ensure_workspace():
    """确保工作区存在"""
    os.makedirs(WORKSPACE_DIR, exist_ok=True)


def check_bootstrap_status() -> bool:
    """检查是否需要引导（user.md不存在则需要引导）"""
    return not os.path.exists(USER_FILE)


def get_bootstrap_prompt() -> str:
    """获取引导提示词"""
    return """请先用 read_file 工具读取 BOOTSTRAP.md，然后按照其指示完成设置。
首次回复要简洁（2-3句话），询问用户名字，然后使用 write_file 将名字写入 user.md。
完成设置后删除 BOOTSTRAP.md。"""


def get_normal_first_greeting() -> str:
    """正常首次问候（2-3句话）"""
    user_name = "friend"
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, 'r') as f:
                content = f.read()
                for line in content.split('\n'):
                    if 'name' in line.lower() or '名字' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            user_name = parts[1].strip().strip('*').strip()
                            break
        except:
            pass
    
    return f"你好 {user_name}！我是 OpenHands。有什么我可以帮你的吗？"


DEFAULT_SYSTEM_PROMPT = """You are OpenHands, a personal AI assistant.

## Workspace Context
Working directory: /workspace

## Your Tools
- terminal_run: Execute commands
- read_file, write_file, list_dir: File operations
- memory_add, memory_search, memory_list: Memory system

## Execution Style
- Actionable request: act in this turn.
- Continue until done or genuinely blocked.
- Keep responses concise (2-3 sentences max for greetings).
- Final answer needs evidence: tool output, file contents, or command result."""


class EmbeddedAgent:
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig.load()
        self.agent_id = self.config.agent_id or f"openhands-{uuid.uuid4().hex[:8]}"
        self._adapter: Optional[ModelAdapter] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._policy_manager: ToolPolicyManager = ToolPolicyManager()
        self._memory: Optional[MemoryStore] = None
        self._sessions: Dict[str, SessionState] = {}
        self._active_runs: Dict[str, EmbeddedAgentRunMeta] = {}
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        logger.info("Initializing OpenHands Agent...")
        ensure_workspace()

        adapter_class = get_adapter_class(self.config.model.provider)
        if not adapter_class:
            raise ValueError(f"Unknown adapter: {self.config.model.provider}")

        self._adapter = adapter_class(self.config.model)
        await self._adapter.initialize()

        self._tool_registry = tool_registry()
        await self._load_core_tools()

        self._initialized = True
        logger.info(f"OpenHands Agent initialized: {self.agent_id}")

    async def _load_core_tools(self):
        from ...tools import file_tools, terminal_tools, memory_tools
        file_tools.register_tools(self._tool_registry)
        terminal_tools.register_tools(self._tool_registry)
        memory_tools.register_tools(self._tool_registry, self._memory)

    async def create_session(self, tool_profile: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
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
        return self._sessions.get(session_id)

    async def queue_message(self, session_id: str, content: str):
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        msg = Message(role=MessageRole.USER, content=content)
        session.messages.append(msg)

    def _to_adapter_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        result = []
        for msg in messages:
            role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            result.append({"role": role, "content": content})
        return result

    def _from_adapter_response(self, response) -> Message:
        if hasattr(response, 'content'):
            return Message(role=MessageRole.ASSISTANT, content=response.content or "")
        return Message(role=MessageRole.ASSISTANT, content=str(response))

    async def run_stream(self, session_id: str, max_iterations: Optional[int] = None, tool_profile: Optional[str] = None, system_prompt_override: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        session = self.get_session(session_id)
        if not session:
            yield {"type": "error", "content": f"Session not found: {session_id}"}
            return

        run_id = str(uuid.uuid4())
        run_meta = EmbeddedAgentRunMeta(run_id=run_id, start_time=datetime.now())
        self._active_runs[run_id] = run_meta
        session.status = SessionStatus.RUNNING

        max_iter = max_iterations or self.config.max_iterations or 30
        budget = IterationBudget(max_total=max_iter)
        tool_results: List[Any] = []

        try:
            async for event in self._agent_loop_stream(session, budget, run_meta, tool_profile, system_prompt_override, tool_results):
                yield event
        except Exception as e:
            logger.exception(f"Agent stream failed: {run_id}")
            yield {"type": "error", "content": str(e)}
        finally:
            session.status = SessionStatus.COMPLETED
            session.updated_at = datetime.now()
            if run_id in self._active_runs:
                del self._active_runs[run_id]

    def _get_system_prompt(self, is_first_message: bool) -> str:
        """根据是否是首次消息返回不同提示词"""
        if is_first_message:
            if check_bootstrap_status():
                return DEFAULT_SYSTEM_PROMPT + "\n\n" + get_bootstrap_prompt()
            else:
                return DEFAULT_SYSTEM_PROMPT + "\n\n" + get_normal_first_greeting()
        return DEFAULT_SYSTEM_PROMPT

    async def _agent_loop_stream(self, session: SessionState, budget: IterationBudget, run_meta: EmbeddedAgentRunMeta, tool_profile: Optional[str], system_prompt_override: Optional[str], tool_results: List[Any]) -> AsyncGenerator[Dict[str, Any], None]:
        profile = tool_profile or session.current_tool_profile or "full"
        
        is_first = len(session.messages) <= 2
        system_prompt = system_prompt_override or self._get_system_prompt(is_first)

        while budget.remaining > 0:
            budget.consume()
            run_meta.iteration_count += 1

            yield {"type": "thinking", "content": f"🧠 思考中..."}

            adapter_messages = self._to_adapter_messages(session.messages)
            tool_defs = self._get_available_tools(profile)

            if hasattr(self._adapter, 'chat_stream') and callable(self._adapter.chat_stream):
                response_text = ""
                pending_tool_calls = []
                
                async for chunk in self._adapter.chat_stream(messages=adapter_messages, tools=tool_defs, system_prompt=system_prompt):
                    if chunk.content:
                        response_text += chunk.content
                        yield {"type": "delta", "content": chunk.content}
                    if chunk.tool_calls and len(chunk.tool_calls) > 0:
                        pending_tool_calls.extend(chunk.tool_calls)
                
                if response_text:
                    assistant_msg = Message(role=MessageRole.ASSISTANT, content=response_text)
                    session.messages.append(assistant_msg)
                
                if pending_tool_calls:
                    for tc in pending_tool_calls:
                        yield {"type": "tool_call", "tool": tc.name, "arguments": tc.arguments}
                        run_meta.tool_call_count += 1
                        
                        actual_tc = ToolCall(id=tc.id, name=tc.name, arguments=tc.arguments)
                        logger.info(f"执行工具: {tc.name}")
                        result = await self._tool_registry.execute_tool_call(actual_tc)
                        tool_results.append(result)
                        
                        yield {"type": "tool_result", "tool": tc.name, "result": result.content[:800] if len(result.content) > 800 else result.content, "is_error": result.is_error}
                        
                        msg = Message(role=MessageRole.TOOL, content=result.content, tool_call_id=tc.id)
                        session.messages.append(msg)
                else:
                    yield {"type": "final", "content": response_text or "任务已完成"}
                    return
            else:
                response = await self._adapter.chat(messages=adapter_messages, tools=tool_defs, system_prompt=system_prompt)
                if response.content:
                    yield {"type": "delta", "content": response.content}
                assistant_msg = self._from_adapter_response(response)
                session.messages.append(assistant_msg)

                if response.tool_calls:
                    for tc in response.tool_calls:
                        yield {"type": "tool_call", "tool": tc.name, "arguments": tc.arguments}
                        result = await self._execute_single_tool(tc, budget, run_meta, profile)
                        tool_results.append(result)
                        yield {"type": "tool_result", "tool": tc.name, "result": result.content[:800] if len(result.content) > 800 else result.content, "is_error": result.is_error}
                        msg = Message(role=MessageRole.TOOL, content=result.content, tool_call_id=tc.id)
                        session.messages.append(msg)
                else:
                    yield {"type": "final", "content": response.content or "处理完成"}
                    return

        yield {"type": "final", "content": "达到最大迭代次数"}

    async def _execute_single_tool(self, tool_call: Any, budget: IterationBudget, run_meta: EmbeddedAgentRunMeta, profile: str) -> Any:
        logger.info(f"Executing tool: {tool_call.name}")
        run_meta.tool_call_count += 1
        
        try:
            tc = ToolCall(id=tool_call.id, name=tool_call.name, arguments=tool_call.arguments)
            result = await self._tool_registry.execute_tool_call(tc)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            from ..types import ToolResult
            return ToolResult(tool_call_id=tool_call.id, content=f"Error: {str(e)}", is_error=True)

    def _get_available_tools(self, profile: str) -> List[Dict[str, Any]]:
        all_defs = self._tool_registry.get_definitions()
        all_names = [d["name"] for d in all_defs]
        allowed_names = self._policy_manager.filter_tools(all_names, profile)
        return [d for d in all_defs if d["name"] in allowed_names}
