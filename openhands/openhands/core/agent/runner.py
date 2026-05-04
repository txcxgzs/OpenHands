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
from .error_prevention import get_error_history, get_prevention_guidance, TrajectoryRecorder
from .tool_repair import repair_tool_call_arguments, coerce_tool_arguments, validate_tool_arguments
from .context_compressor import ContextCompressor, should_compress
from .tool_guardrails import ToolGuardrailController, ToolGuardrailConfig
from .interrupt_control import InterruptController, ProgressTracker, get_interrupt_controller
from .delegation import DelegationManager, DelegationConfig

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


def get_bootstrap_context() -> str:
    """获取BOOTSTRAP.md内容作为上下文"""
    if os.path.exists(BOOTSTRAP_FILE):
        try:
            with open(BOOTSTRAP_FILE, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            pass
    return ""


def get_bootstrap_prompt() -> str:
    """获取引导提示词 - 直接内嵌BOOTSTRAP.md内容"""
    bootstrap_content = get_bootstrap_context()
    if bootstrap_content:
        return f"""## 首次设置任务
必须按顺序完成以下步骤：

{bootstrap_content}

## 强制规则
- 回复必须控制在2-3句话以内
- 先调用工具再回复，不要只输出文字指令
- 绝对不要说超过3句话"""
    return """## 首次设置任务
1. 询问用户名字（2-3句话）
2. 用户回复后用 write_file 保存到 user.md
3. 用 terminal_run 删除 BOOTSTRAP.md
- 回复必须控制在2-3句话以内"""


def get_normal_first_greeting() -> str:
    """正常首次问候（2-3句话）"""
    user_name = "朋友"
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


DEFAULT_SYSTEM_PROMPT = """你是 OpenHands，一个强大的智能助手。

## 工作区
工作目录: /workspace/openhands-workspace

## 你的工具（详细说明）
### 终端工具
- terminal_run: 在当前目录执行终端命令，返回输出结果
  - 参数: command (字符串，必需)
  - 示例: {"command": "ls -la"}

### 文件工具
- read_file: 读取文件内容
  - 参数: file_path (字符串，必需)
  - 示例: {"file_path": "/workspace/openhands-workspace/test.py"}
- write_file: 写入文件内容（创建新文件或覆盖现有文件）
  - 参数: file_path (字符串，必需), content (字符串，必需)
  - 示例: {"file_path": "test.py", "content": "print('Hello')"}
- list_dir: 列出目录内容
  - 参数: dir_path (字符串，可选，默认当前目录)
  - 示例: {"dir_path": "/workspace/openhands-workspace"}
- edit_file: 编辑文件内容（替换文本）
  - 参数: file_path (字符串，必需), old_string (字符串，必需), new_string (字符串，必需)
  - 示例: {"file_path": "test.py", "old_string": "old", "new_string": "new"}

### 记忆工具
- memory_add: 添加记忆条目
  - 参数: key (字符串，必需), value (字符串，必需)
  - 示例: {"key": "user_preference", "value": "喜欢简洁的回复"}
- memory_search: 搜索记忆
  - 参数: query (字符串，必需)
  - 示例: {"query": "user_preference"}
- memory_list: 列出所有记忆

### 网页工具
- web_search: 使用DuckDuckGo搜索网络
  - 参数: query (字符串，必需), limit (数字，可选，默认5)
  - 示例: {"query": "Python asyncio 教程", "limit": 3}
- web_fetch: 获取网页HTML内容
  - 参数: url (字符串，必需), max_length (数字，可选，默认4000)
  - 示例: {"url": "https://example.com"}

### 沙箱工具
- sandbox_exec: 在沙箱中执行代码
  - 参数: code (字符串，必需), language (字符串，可选，默认python)
  - 示例: {"code": "print(1+1)", "language": "python"}
- sandbox_check: 检查沙箱状态

## 执行规则
1. 可执行的请求：立即调用工具执行，不要只输出文字指令
2. 持续直到完成或真正被阻塞
3. 使用工具前先思考为什么要使用
4. 回复简洁：问候语不超过2-3句话
5. 回答需要证据：引用工具输出、文件内容或命令结果

## 工具调用技巧
- 复杂任务分解成多个步骤，一步一步完成
- 使用多个工具协同工作
- 遇到错误时重试或换方法
- 优先使用效率高的工具
- 编辑文件时，先read_file读取，确认内容后再edit_file
- 执行终端命令时，小步快跑，每次只做一件事

## 重要：回复长度限制
- 问候语必须控制在2-3句话以内
- 禁止长篇大论
- 简洁是美德
- 工作时用工具行动，而不是空谈
- 工具调用是你的主要工作方式，先调用工具，再用简短语言总结结果"""


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

        # 初始化 memory store
        from ...core.memory.store import MemoryStore
        self._memory = MemoryStore(path="./data/memory")

        self._tool_registry = tool_registry()
        await self._load_core_tools()

        self._initialized = True
        logger.info(f"OpenHands Agent initialized: {self.agent_id}")
        
        # 初始化错误历史记录
        self._error_history = get_error_history()
        self._prevention = get_prevention_guidance()
        
        # 初始化上下文压缩器
        self._context_compressor = ContextCompressor(
            context_limit=128000,
            threshold_percent=0.75
        )

    async def _load_core_tools(self):
        from ...tools import file_tools, terminal_tools, memory_tools
        from ...tools import web_tools, browser_tools, voice_tools, media_tools, sandbox_tools
        
        file_tools.register_tools(self._tool_registry)
        terminal_tools.register_tools(self._tool_registry)
        memory_tools.register_tools(self._tool_registry, self._memory)
        web_tools.register_tools(self._tool_registry)
        browser_tools.register_tools(self._tool_registry)
        voice_tools.register_tools(self._tool_registry)
        media_tools.register_tools(self._tool_registry)
        sandbox_tools.register_tools(self._tool_registry)

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
            run_meta.success = False
            run_meta.error_count += 1
            yield {"type": "error", "content": str(e)}
            # 记录失败轨迹
            messages = [{"role": m.role.value, "content": m.content} for m in session.messages]
            TrajectoryRecorder.save_trajectory(
                messages=messages,
                model=self.config.model.model,
                completed=False,
                error=str(e)
            )
        finally:
            session.status = SessionStatus.COMPLETED
            session.updated_at = datetime.now()
            if run_id in self._active_runs:
                del self._active_runs[run_id]
            
            # 保存成功轨迹
            if run_meta.success and len(session.messages) > 2:
                messages = [{"role": m.role.value, "content": m.content} for m in session.messages]
                TrajectoryRecorder.save_trajectory(
                    messages=messages,
                    model=self.config.model.model,
                    completed=True
                )

    def _get_system_prompt(self, is_first_message: bool) -> str:
        """根据是否是首次消息返回不同提示词"""
        base_prompt = DEFAULT_SYSTEM_PROMPT
        
        # 添加错误历史指导
        if hasattr(self, '_prevention'):
            guidance = self._prevention.get_system_guidance()
            if guidance:
                base_prompt += guidance
        
        if is_first_message:
            if check_bootstrap_status():
                return base_prompt + "\n\n" + get_bootstrap_prompt()
            else:
                return base_prompt + "\n\n" + get_normal_first_greeting()
        return base_prompt

    async def _agent_loop_stream(self, session: SessionState, budget: IterationBudget, run_meta: EmbeddedAgentRunMeta, tool_profile: Optional[str], system_prompt_override: Optional[str], tool_results: List[Any]) -> AsyncGenerator[Dict[str, Any], None]:
        profile = tool_profile or session.current_tool_profile or "full"
        
        is_first = len(session.messages) <= 2
        system_prompt = system_prompt_override or self._get_system_prompt(is_first)
        
        consecutive_errors = 0
        max_consecutive_errors = 3

        while budget.remaining > 0:
            budget.consume()
            run_meta.iteration_count += 1

            # 检查是否需要上下文压缩
            if self._context_compressor.should_compress(self._to_adapter_messages(session.messages)):
                yield {"type": "thinking", "content": f"📝 上下文较长，正在压缩..."}
                compressed_messages = self._context_compressor.compress(
                    self._to_adapter_messages(session.messages),
                    model=self.config.model.model
                )
                # 更新session中的消息
                session.messages = [Message(role=MessageRole(role), content=content) 
                                   for role, content in [(m['role'], m['content']) for m in compressed_messages]]
                yield {"type": "context_compressed", "content": "上下文已压缩"}
            
            yield {"type": "thinking", "content": f"🧠 思考中..."}

            adapter_messages = self._to_adapter_messages(session.messages)
            tool_defs = self._get_available_tools(profile)

            try:
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
                        consecutive_errors = 0
                        for tc in pending_tool_calls:
                            yield {"type": "tool_call", "tool": tc.name, "arguments": tc.arguments}
                            run_meta.tool_call_count += 1
                            
                            actual_tc = ToolCall(id=tc.id, name=tc.name, arguments=tc.arguments)
                            logger.info(f"执行工具: {tc.name}")
                            result = await self._tool_registry.execute_tool_call(actual_tc)
                            tool_results.append(result)
                            
                            # 记录错误历史
                            if result.is_error:
                                self._error_history.record_tool_error(tc.name, result.content, tc.arguments)
                                run_meta.error_count += 1
                                consecutive_errors += 1
                                yield {"type": "tool_result", "tool": tc.name, "result": result.content[:800] if len(result.content) > 800 else result.content, "is_error": True}
                                if consecutive_errors >= max_consecutive_errors:
                                    yield {"type": "error", "content": "连续错误过多，停止执行"}
                                    return
                            else:
                                self._error_history.record_tool_success(tc.name)
                                yield {"type": "tool_result", "tool": tc.name, "result": result.content[:800] if len(result.content) > 800 else result.content, "is_error": False}
                            
                            msg = Message(role=MessageRole.TOOL, content=result.content, tool_call_id=tc.id)
                            session.messages.append(msg)
                    else:
                        # 检查是否真的完成了任务
                        if self._is_task_completed(response_text):
                            yield {"type": "final", "content": response_text or "任务已完成"}
                            return
                        # 如果没有工具调用但有内容，可能是需要更多信息
                        yield {"type": "final", "content": response_text or "处理完成"}
                        return
                else:
                    response = await self._adapter.chat(messages=adapter_messages, tools=tool_defs, system_prompt=system_prompt)
                    if response.content:
                        yield {"type": "delta", "content": response.content}
                    assistant_msg = self._from_adapter_response(response)
                    session.messages.append(assistant_msg)

                    if response.tool_calls:
                        consecutive_errors = 0
                        for tc in response.tool_calls:
                            yield {"type": "tool_call", "tool": tc.name, "arguments": tc.arguments}
                            result = await self._execute_single_tool(tc, budget, run_meta, profile)
                            tool_results.append(result)
                            
                            # 记录错误历史
                            if result.is_error:
                                self._error_history.record_tool_error(tc.name, result.content, tc.arguments)
                                run_meta.error_count += 1
                                consecutive_errors += 1
                                yield {"type": "tool_result", "tool": tc.name, "result": result.content[:800] if len(result.content) > 800 else result.content, "is_error": True}
                                if consecutive_errors >= max_consecutive_errors:
                                    yield {"type": "error", "content": "连续错误过多，停止执行"}
                                    return
                            else:
                                self._error_history.record_tool_success(tc.name)
                                yield {"type": "tool_result", "tool": tc.name, "result": result.content[:800] if len(result.content) > 800 else result.content, "is_error": False}
                            
                            msg = Message(role=MessageRole.TOOL, content=result.content, tool_call_id=tc.id)
                            session.messages.append(msg)
                    else:
                        if self._is_task_completed(response.content if hasattr(response, 'content') else str(response)):
                            yield {"type": "final", "content": response.content or "任务已完成"}
                            return
                        yield {"type": "final", "content": response.content or "处理完成"}
                        return
                        
            except Exception as e:
                logger.exception("Agent loop error")
                yield {"type": "error", "content": f"执行出错: {str(e)}"}
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    yield {"type": "error", "content": "连续错误过多，停止执行"}
                    return

        yield {"type": "final", "content": "达到最大迭代次数"}
    
    def _is_task_completed(self, text: str) -> bool:
        """检测任务是否完成"""
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # 完成关键词
        completed_keywords = [
            "完成了", "任务完成", "done", "finished", "completed",
            "已经搞定", "搞定了", "解决了", "all done",
            "success", "successful", "成功"
        ]
        
        for keyword in completed_keywords:
            if keyword in text_lower:
                return True
        
        # 检查是否只是问候语或简单响应
        simple_responses = ["你好", "hello", "hi", "有什么", "帮您"]
        if any(text_lower.startswith(k) for k in simple_responses) and len(text) < 50:
            return False
        
        return False

    async def _execute_single_tool(self, tool_call: Any, budget: IterationBudget, run_meta: EmbeddedAgentRunMeta, profile: str) -> Any:
        logger.info(f"Executing tool: {tool_call.name}")
        run_meta.tool_call_count += 1
        
        try:
            # 1. 修复工具调用参数（Hermes风格的JSON修复）
            raw_args = tool_call.arguments
            if isinstance(raw_args, str):
                repaired_args = repair_tool_call_arguments(raw_args, tool_call.name)
                import json
                try:
                    arguments = json.loads(repaired_args)
                except json.JSONDecodeError:
                    arguments = {}
            elif isinstance(raw_args, dict):
                arguments = raw_args
            else:
                arguments = {}
            
            # 2. 类型强制转换
            tool_def = self._tool_registry.get_tool(tool_call.name)
            if tool_def and hasattr(tool_def, 'parameters'):
                arguments = coerce_tool_arguments(arguments, {'parameters': tool_def.parameters})
            
            # 3. 执行工具
            tc = ToolCall(id=tool_call.id, name=tool_call.name, arguments=arguments)
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
        result = []
        for d in all_defs:
            if d["name"] in allowed_names:
                result.append(d)
        return result
