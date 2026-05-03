"""
AuroraAgent 核心 Agent Loop
深度参考: OpenClaw Agent Loop, Hermes Agent AIAgent
"""

import asyncio
import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from .config import AgentConfig
from .adapters.base import ModelAdapter, NormalizedResponse
from .adapters.anthropic_adapter import AnthropicAdapter
from ..tools.registry import ToolRegistry, ToolResult, tool_registry

logger = logging.getLogger(__name__)


@dataclass
class IterationBudget:
    """迭代预算 - 线程安全"""
    max_total: int
    _used: int = 0
    _lock: threading.Lock = threading.Lock()
    
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
class AgentResponse:
    """Agent 执行响应"""
    messages: List[Dict[str, Any]]
    iteration_count: int = 0
    final_answer: Optional[str] = None
    tool_errors: List[Dict] = None


SYSTEM_PROMPT = """你是 Aurora，一个强大的 Windows AI 助手。

你可以：
- 控制鼠标和键盘
- 查看和操作窗口
- 捕获屏幕
- 执行终端命令
- 读写文件
- 进行多模态交互（处理图像）

重要说明：
1. 优先使用安全方法
2. 每次执行工具后，等待结果再继续
3. 复杂操作分步骤进行
4. 保持解释性和透明度

现在，准备好帮助用户！
"""


class AuroraAgent:
    """
    主 Agent 类 - 深度整合 OpenClaw 和 Hermes Agent 设计
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig.load()
        self._adapter: Optional[ModelAdapter] = None
        self._registry: Optional[ToolRegistry] = None
        self._initialized = False
        self._messages: List[Dict[str, Any]] = []
        self._iteration_count = 0
        self._tool_errors: List[Dict] = []
    
    async def initialize(self):
        """初始化 Agent"""
        if self._initialized:
            return
        
        # 初始化工具注册表
        self._registry = tool_registry()
        
        # 加载工具集
        await self._load_toolsets()
        
        # 初始化模型适配器
        self._adapter = await self._create_adapter()
        
        self._initialized = True
        logger.info("AuroraAgent initialized")
    
    async def _load_toolsets(self):
        """加载工具集"""
        from ..tools import file_tools
        from ..tools import terminal_tools
        from ..windows import windows_tools
        from ..multimodal import multimodal_tools
        
        file_tools.register_tools(self._registry)
        terminal_tools.register_tools(self._registry)
        windows_tools.register_tools(self._registry)
        multimodal_tools.register_tools(self._registry)
        
        logger.info(f"Loaded toolsets: {self._registry.list_toolsets()}")
    
    async def _create_adapter(self) -> ModelAdapter:
        """创建模型适配器"""
        provider = self.config.model.provider
        
        if provider == "anthropic":
            adapter = AnthropicAdapter()
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        await adapter.initialize(self.config.model)
        return adapter
    
    async def chat(
        self,
        user_message: str,
        images: Optional[List[str]] = None,
        max_iterations: Optional[int] = None,
    ) -> AgentResponse:
        """
        主要聊天接口
        
        Args:
            user_message: 用户消息
            images: 可选的图像路径列表
            max_iterations: 最大迭代次数
        
        Returns:
            AgentResponse
        """
        if not self._initialized:
            await self.initialize()
        
        max_iter = max_iterations or self.config.max_iterations
        budget = IterationBudget(max_total=max_iter)
        
        # 添加用户消息
        user_msg = self._build_user_message(user_message, images)
        self._messages.append(user_msg)
        
        # 执行 Agent Loop
        final_response = await self._agent_loop(budget)
        
        return final_response
    
    def _build_user_message(
        self,
        text: str,
        images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """构建用户消息（支持多模态）"""
        if not images:
            return {"role": "user", "content": text}
        
        content = [{"type": "text", "text": text}]
        
        for img_path in images:
            img_block = self._load_image_as_block(img_path)
            content.append(img_block)
        
        return {"role": "user", "content": content}
    
    def _load_image_as_block(self, path: str) -> Dict[str, Any]:
        """加载图像为消息块"""
        import base64
        from pathlib import Path
        from PIL import Image
        import io
        
        img_path = Path(path)
        if not img_path.exists():
            return {"type": "text", "text": f"[Image not found: {path}]"}
        
        # 打开并优化图像
        with Image.open(img_path) as img:
            # 转换为 RGB
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # 调整大小（如需要）
            max_size = 1568
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 转换为 base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            img_data = base64.b64encode(buffer.getvalue()).decode()
        
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_data,
            },
        }
    
    async def _agent_loop(self, budget: IterationBudget) -> AgentResponse:
        """主 Agent Loop - 深度参考 OpenClaw 和 Hermes"""
        
        tool_errors = []
        
        while budget.remaining > 0:
            # 1. 准备调用
            tools = self._get_available_tools()
            
            # 2. 调用模型
            budget.consume()
            self._iteration_count += 1
            
            response = await self._adapter.call(
                messages=self._messages,
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
            )
            
            # 3. 添加助手消息
            assistant_msg = self._build_assistant_message(response)
            self._messages.append(assistant_msg)
            
            # 4. 检查工具调用
            if response.tool_calls:
                # 执行工具
                await self._execute_tool_calls(response.tool_calls, budget, tool_errors)
            else:
                # 无工具调用，结束
                return AgentResponse(
                    messages=self._messages,
                    iteration_count=self._iteration_count,
                    final_answer=response.content,
                    tool_errors=tool_errors,
                )
        
        # 达到最大迭代
        return AgentResponse(
            messages=self._messages,
            iteration_count=self._iteration_count,
            final_answer="已达到最大迭代次数。",
            tool_errors=tool_errors,
        )
    
    def _get_available_tools(self) -> List[Dict]:
        """获取可用工具列表"""
        return self._registry.get_definitions(
            enabled_toolsets=set(self.config.enabled_toolsets),
            disabled_toolsets=set(self.config.disabled_toolsets),
        )
    
    def _build_assistant_message(self, response: NormalizedResponse) -> Dict[str, Any]:
        """构建助手消息"""
        msg = {"role": "assistant", "content": response.content}
        
        if response.tool_calls:
            msg["tool_calls"] = response.tool_calls
        
        return msg
    
    async def _execute_tool_calls(
        self,
        tool_calls: List[Dict],
        budget: IterationBudget,
        tool_errors: List[Dict],
    ):
        """执行工具调用"""
        tool_results = []
        
        # 检查是否可并行执行
        if _should_parallelize_tool_batch(tool_calls):
            results = await asyncio.gather(
                *[self._execute_single_tool(tc, budget, tool_errors) for tc in tool_calls],
                return_exceptions=True,
            )
            
            for tc, result in zip(tool_calls, results):
                if isinstance(result, Exception):
                    tool_errors.append({
                        "tool": tc.get("name"),
                        "error": str(result),
                    })
                    tool_results.append(self._error_tool_result(tc.get("id"), str(result)))
                else:
                    tool_results.append(result)
        else:
            for tc in tool_calls:
                result = await self._execute_single_tool(tc, budget, tool_errors)
                tool_results.append(result)
        
        # 添加工具结果消息
        self._messages.append({
            "role": "user",
            "content": tool_results,
        })
    
    async def _execute_single_tool(
        self,
        tool_call: Dict,
        budget: IterationBudget,
        tool_errors: List[Dict],
    ) -> Dict[str, Any]:
        """执行单个工具"""
        tool_id = tool_call.get("id", "")
        name = tool_call.get("name", "")
        arguments = tool_call.get("arguments", {})
        
        # 修复参数格式
        arguments = _repair_tool_call_arguments(arguments, name)
        
        logger.info(f"Executing tool: {name} with: {arguments}")
        
        result = await self._registry.execute_tool(name, arguments)
        
        if not result.success:
            tool_errors.append({
                "tool": name,
                "error": result.error,
            })
            budget.refund()
        
        return {
            "tool_call_id": tool_id,
            "role": "tool",
            "content": result.output or result.error or "",
        }
    
    def _error_tool_result(self, tool_id: str, error: str) -> Dict[str, Any]:
        return {
            "tool_call_id": tool_id,
            "role": "tool",
            "content": f"Error: {error}",
        }
    
    def clear_history(self):
        """清空聊天历史"""
        self._messages = []
        self._iteration_count = 0


# 工具调用参数修复
def _repair_tool_call_arguments(args: Any, tool_name: str) -> Dict:
    """修复模型生成的无效参数格式"""
    if isinstance(args, dict):
        return args
    
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            pass
    
    logger.warning(f"Invalid arguments for {tool_name}: {args}")
    return {}


# 并行执行判断
def _should_parallelize_tool_batch(tool_calls: List[Dict]) -> bool:
    """判断工具调用批次是否可以并行执行"""
    if len(tool_calls) <= 1:
        return True
    
    # 检查是否有不允许并行的工具
    serial_tools = {
        "confirm", "pause", "mouse_click", "mouse_drag", "key_press",
    }
    
    names = {tc.get("name", "") for tc in tool_calls}
    if names & serial_tools:
        return False
    
    # 检查是否有路径冲突
    read_write_tools = {"read_file", "write_file", "delete_file"}
    if len(names & read_write_tools) > 1:
        return False
    
    return True
