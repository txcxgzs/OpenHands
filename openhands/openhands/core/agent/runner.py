
"""
Agent Runtime - Deep reference to OpenClaw's pi-embedded-runner
"""

from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import threading
import uuid
import logging
import json

from ..types import (
    Message, MessageContentBlock, ToolCall, ToolResult,
    NormalizedResponse, AgentRunMeta, AgentRunResult,
    MessageRole, SessionState, SessionStatus,
)
from ..config import AgentConfig
from ..adapters import ModelAdapter, get_adapter_class
from ...tools import file_tools, terminal_tools, memory_tools
from ..tools.registry import ToolRegistry, tool_registry
from ..tools.policy import ToolPolicyManager
from ..memory.store import MemoryStore

logger = logging.getLogger(__name__)


@dataclass
class IterationBudget:
    """Iteration budget with thread safety"""
    max_total: int
    _used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def consume(self) -> bool:
        with self._lock:
            if self._used >= self.max_total:
                return False
            self._used += 1
            return True

    def refund(self) -> None:
        with self._lock:
            if self._used > 0:
                self._used -= 1

    @property
    def remaining(self) -> int:
        with self._lock:
            return max(0, self.max_total - self._used)

    @property
    def used(self) -> int:
        with self._lock:
            return self._used


@dataclass
class EmbeddedAgentMeta:
    """Embedded agent metadata - Reference OpenClaw"""
    agent_id: str
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    tool_profile: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddedAgentRunMeta:
    """Run metadata"""
    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    iteration_count: int = 0
    tool_call_count: int = 0
    error_count: int = 0
    success: bool = True


@dataclass
class EmbeddedAgentRunResult:
    """Run result - Reference OpenClaw"""
    meta: EmbeddedAgentRunMeta
    final_answer: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


DEFAULT_SYSTEM_PROMPT = """You are Aurora, a powerful AI assistant.

You can use tools to help the user. You have access to:
- Memory system to store and retrieve information
- File operations to read and write files
- Terminal to run commands
- Windows automation to control the desktop
- Web search and browsing

Use the tools appropriately and explain what you are doing.
"""


class EmbeddedAgent:
    """
    Embedded Agent - Core runtime
    Deep reference to OpenClaw's embedded agent
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig.load()
        self.agent_id = self.config.agent_id or f"aurora-{uuid.uuid4().hex[:8]}"

        self._adapter: Optional[ModelAdapter] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._policy_manager: ToolPolicyManager = ToolPolicyManager()
        self._memory: Optional[MemoryStore] = None

        self._sessions: Dict[str, SessionState] = {}
        self._active_runs: Dict[str, EmbeddedAgentRunMeta] = {}
        self._initialized = False

    @property
    def tool_registry(self) -> ToolRegistry:
        """获取工具注册表"""
        return self._tool_registry

    async def initialize(self):
        """Initialize agent components"""
        if self._initialized:
            return

        self._tool_registry = tool_registry()
        self._memory = MemoryStore(self.config.memory.path)

        await self._load_core_tools()
        await self._init_adapter()

        self._initialized = True
        logger.info(f"EmbeddedAgent initialized: {self.agent_id}")

    async def _init_adapter(self):
        """Initialize model adapter"""
        adapter_cls = get_adapter_class(self.config.model.provider)
        if not adapter_cls:
            raise ValueError(f"Unsupported provider: {self.config.model.provider}")
        self._adapter = adapter_cls(self.config.model)
        await self._adapter.initialize()

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
        """Create a new session - Reference OpenClaw"""
        session_id = str(uuid.uuid4())

        state = SessionState(
            session_id=session_id,
            status=SessionStatus.IDLE,
            current_tool_profile=tool_profile,
            metadata=metadata or {},
        )

        self._sessions[session_id] = state
        logger.debug(f"Created session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session state"""
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[SessionState]:
        """List all sessions"""
        return list(self._sessions.values())

    async def queue_message(
        self,
        session_id: str,
        content: str,
        images: Optional[List[str]] = None,
    ) -> Message:
        """Queue message to session - Reference OpenClaw"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        msg_content = [MessageContentBlock(type="text", text=content)]

        if images:
            for img in images:
                img_block = await self._load_image_block(img)
                msg_content.append(img_block)

        message = Message(
            role=MessageRole.USER,
            content=msg_content,
        )

        session.messages.append(message)
        session.updated_at = datetime.now()

        await self._memory.add(content, {
            "type": "user_message",
            "session_id": session_id,
        })

        return message

    async def _load_image_block(self, path: str) -> MessageContentBlock:
        """Load image as message content block"""
        import base64
        from pathlib import Path
        from PIL import Image
        import io

        img_path = Path(path)
        if not img_path.exists():
            return MessageContentBlock(type="text", text=f"[Image not found: {path}]")

        with Image.open(img_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            max_size = 1568
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            img_data = base64.b64encode(buffer.getvalue()).decode()

        return MessageContentBlock(
            type="image",
            source={
                "type": "base64",
                "media_type": "image/png",
                "data": img_data,
            },
        )

    async def run(
        self,
        session_id: str,
        max_iterations: Optional[int] = None,
        tool_profile: Optional[str] = None,
        system_prompt_override: Optional[str] = None,
    ) -> EmbeddedAgentRunResult:
        """
        Main agent run - Reference OpenClaw's pi-embedded-runner
        """
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

        max_iter = max_iterations or self.config.max_iterations
        budget = IterationBudget(max_total=max_iter)
        tool_results: List[ToolResult] = []

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
            run_meta.end_time = datetime.now()
            session.status = SessionStatus.COMPLETED
            session.updated_at = datetime.now()
            if run_id in self._active_runs:
                del self._active_runs[run_id]

    async def _agent_loop(
        self,
        session: SessionState,
        budget: IterationBudget,
        run_meta: EmbeddedAgentRunMeta,
        tool_profile: Optional[str],
        system_prompt_override: Optional[str],
        tool_results: List[ToolResult],
    ) -> EmbeddedAgentRunResult:
        """
        Core agent loop - Reference OpenClaw
        """
        profile = tool_profile or session.current_tool_profile or self.config.tools.default_profile
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
                await self._execute_tool_calls(
                    tool_calls=response.tool_calls,
                    session=session,
                    budget=budget,
                    run_meta=run_meta,
                    tool_results=tool_results,
                    profile=profile,
                )
            else:
                if response.content:
                    await self._memory.add(response.content, {
                        "type": "assistant_message",
                        "session_id": session.session_id,
                    })

                return EmbeddedAgentRunResult(
                    meta=run_meta,
                    final_answer=response.content,
                    messages=session.messages,
                    tool_results=tool_results,
                    success=True,
                )

        return EmbeddedAgentRunResult(
            meta=run_meta,
            final_answer="Maximum iterations reached.",
            messages=session.messages,
            tool_results=tool_results,
            success=True,
        )

    def _to_adapter_messages(self, messages: List[Message]) -> List[Message]:
        """Convert to adapter message format"""
        return messages

    def _from_adapter_response(self, response: NormalizedResponse) -> Message:
        """Convert adapter response to message"""
        return Message(
            role=MessageRole.ASSISTANT,
            content=response.content or "",
            tool_calls=response.tool_calls,
        )

    def _get_available_tools(self, profile: str) -> List[Dict[str, Any]]:
        """Get filtered tools based on policy"""
        all_defs = self._tool_registry.get_definitions()
        all_names = [d["name"] for d in all_defs]
        allowed_names = self._policy_manager.filter_tools(all_names, profile)

        return [d for d in all_defs if d["name"] in allowed_names]

    async def _execute_tool_calls(
        self,
        tool_calls: List[ToolCall],
        session: SessionState,
        budget: IterationBudget,
        run_meta: EmbeddedAgentRunMeta,
        tool_results: List[ToolResult],
        profile: str,
    ):
        """Execute tool calls - Reference OpenClaw"""
        if _should_parallelize_tool_batch(tool_calls):
            tasks = [
                self._execute_single_tool(tc, budget, run_meta, profile)
                for tc in tool_calls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for tc, result in zip(tool_calls, results):
                if isinstance(result, Exception):
                    logger.error(f"Tool failed: {tc.name}", exc_info=result)
                    tool_result = ToolResult(
                        tool_call_id=tc.id,
                        content=f"Error: {str(result)}",
                        is_error=True,
                    )
                    tool_results.append(tool_result)
                    run_meta.error_count += 1
                else:
                    tool_results.append(result)

                msg = Message(
                    role=MessageRole.TOOL,
                    content=result.content if isinstance(result, ToolResult) else str(result),
                    tool_call_id=tc.id,
                )
                session.messages.append(msg)
        else:
            for tc in tool_calls:
                result = await self._execute_single_tool(tc, budget, run_meta, profile)
                tool_results.append(result)
                msg = Message(
                    role=MessageRole.TOOL,
                    content=result.content,
                    tool_call_id=tc.id,
                )
                session.messages.append(msg)

    async def _execute_single_tool(
        self,
        tool_call: ToolCall,
        budget: IterationBudget,
        run_meta: EmbeddedAgentRunMeta,
        profile: str,
    ) -> ToolResult:
        """Execute single tool"""
        tool_call.arguments = _repair_tool_call_arguments(tool_call.arguments, tool_call.name)

        logger.info(f"Executing tool: {tool_call.name}")
        run_meta.tool_call_count += 1

        if self._policy_manager.check_approval(tool_call.name, profile):
            logger.warning(f"Tool {tool_call.name} requires approval (skipped)")
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Tool '{tool_call.name}' requires explicit approval.",
                is_error=True,
            )

        result = await self._tool_registry.execute_tool_call(tool_call)

        if result.is_error:
            budget.refund()
            run_meta.error_count += 1

        return result


def _repair_tool_call_arguments(args: Any, tool_name: str) -> Dict[str, Any]:
    """Repair invalid tool call arguments"""
    if isinstance(args, dict):
        return args

    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            pass

    logger.warning(f"Invalid arguments for {tool_name}: {args}")
    return {}


def _should_parallelize_tool_batch(tool_calls: List[ToolCall]) -> bool:
    """Decide if tool calls should be parallelized"""
    if len(tool_calls) <= 1:
        return True

    serial_tools = {"confirm", "pause", "mouse_click", "key_press"}
    for tc in tool_calls:
        if tc.name in serial_tools:
            return False

    return True
