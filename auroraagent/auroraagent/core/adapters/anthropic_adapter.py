"""
Anthropic Claude 模型适配器
参考: Hermes Agent Anthropic Adapter
"""

import base64
import os
from typing import Any, Dict, List, Optional
import logging

from .base import ModelAdapter, NormalizedResponse

logger = logging.getLogger(__name__)

# 延迟导入，避免启动开销
_ANTHROPIC_CLS_CACHE: Optional[type] = None


def _load_anthropic_cls() -> type:
    global _ANTHROPIC_CLS_CACHE
    if _ANTHROPIC_CLS_CACHE is None:
        from anthropic import Anthropic as _cls
        _ANTHROPIC_CLS_CACHE = _cls
    return _ANTHROPIC_CLS_CACHE


class AnthropicAdapter(ModelAdapter):
    """Anthropic Claude 适配器"""
    
    # 模型输出限制
    _ANTHROPIC_OUTPUT_LIMITS = {
        "claude-opus-4-7": 128000,
        "claude-opus-4-6": 128000,
        "claude-sonnet-4-6": 64000,
        "claude-sonnet-3-5": 8192,
        "claude-3-opus": 4096,
        "claude-3-sonnet": 4096,
        "claude-3-haiku": 4096,
    }
    
    def __init__(self):
        self._client = None
        self._config = None
        self._initialized = False
    
    @property
    def provider(self) -> str:
        return "anthropic"
    
    async def initialize(self, config: Any):
        """初始化 Anthropic 客户端"""
        if self._initialized:
            return
        
        self._config = config
        api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        
        AnthropicCls = _load_anthropic_cls()
        self._client = AnthropicCls(api_key=api_key)
        self._initialized = True
    
    async def call(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> NormalizedResponse:
        """调用 Claude 模型"""
        if not self._initialized:
            raise RuntimeError("Adapter not initialized")
        
        anthropic_system, anthropic_messages = self.convert_messages(
            messages, system_prompt
        )
        anthropic_tools = self.convert_tools(tools) if tools else None
        
        max_tokens = kwargs.get("max_tokens", self._config.max_tokens)
        temperature = kwargs.get("temperature", self._config.temperature)
        
        # 调用模型（同步转换为异步）
        response = await self._call_with_client(
            model=self._config.model,
            system=anthropic_system,
            messages=anthropic_messages,
            tools=anthropic_tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        return self._normalize_response(response)
    
    async def _call_with_client(self, **kwargs):
        """在线程池中调用客户端"""
        import asyncio
        loop = asyncio.get_running_loop()
        
        def _sync_call():
            return self._client.messages.create(**kwargs)
        
        return await loop.run_in_executor(None, _sync_call)
    
    def convert_messages(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> tuple[Optional[str], List[Dict]]:
        """转换消息到 Anthropic 格式"""
        system_segments = []
        anthropic_messages = []
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            if role == "system":
                if system_prompt:
                    system_segments.append(content)
                else:
                    system_prompt = content
            else:
                anthropic_msg = self._convert_single_message(msg)
                anthropic_messages.append(anthropic_msg)
        
        if system_segments:
            combined_system = system_prompt + "\n\n" + "\n\n".join(system_segments)
            return combined_system, anthropic_messages
        
        return system_prompt, anthropic_messages
    
    def _convert_single_message(self, msg: Dict[str, Any]) -> Dict:
        """转换单条消息"""
        role = msg.get("role")
        content = msg.get("content")
        
        # 处理多模态内容
        if isinstance(content, list):
            processed_content = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "image":
                        processed_content.append(self._convert_image(part))
                    else:
                        processed_content.append(part)
                else:
                    processed_content.append({"type": "text", "text": str(part)})
            content = processed_content
        
        if role == "assistant":
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                content.extend(self._convert_tool_calls(tool_calls))
        
        return {"role": role, "content": content}
    
    def _convert_image(self, image_data: Dict) -> Dict:
        """转换图像数据"""
        source = image_data.get("source", {})
        media_type = source.get("media_type", "image/png")
        data = source.get("data")
        
        if data and not data.startswith("data:"):
            data = base64.b64encode(data).decode() if isinstance(data, bytes) else data
        
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data,
            },
        }
    
    def _convert_tool_calls(self, tool_calls: List[Dict]) -> List[Dict]:
        """转换工具调用格式"""
        return [
            {
                "type": "tool_use",
                "id": tc.get("id", ""),
                "name": tc.get("name", ""),
                "input": tc.get("arguments", {}),
            }
            for tc in tool_calls
        ]
    
    def convert_tools(self, tools: List[Dict]) -> List[Dict]:
        """转换工具到 Anthropic 格式"""
        converted = []
        for tool in tools:
            if tool.get("type") == "function":
                fn = tool.get("function", {})
                converted.append({
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                })
        return converted
    
    def _normalize_response(self, response) -> NormalizedResponse:
        """标准化响应"""
        content = ""
        tool_calls = []
        reasoning = None
        
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })
        
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        }
        
        return NormalizedResponse(
            content=content,
            tool_calls=tool_calls if tool_calls else None,
            reasoning=reasoning,
            usage=usage,
        )
