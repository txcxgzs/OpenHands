"""
LongCat API Adapter
支持 LongCat-2.0-Preview 模型
API: https://api.longcat.chat/openai/v1
"""

from typing import Dict, List, Optional, Any, AsyncGenerator
import json
import logging
import asyncio
from .base import ModelAdapter, NormalizedResponse, ToolCall, Message

logger = logging.getLogger(__name__)


class LongCatAdapter(ModelAdapter):
    """
    LongCat AI 模型适配器
    支持 LongCat-2.0-Preview, LongCat-Flash-Chat, LongCat-Flash-Thinking
    
    API格式: OpenAI兼容
    文档: https://longcat.chat/platform/docs/zh/
    """
    
    BASE_URL = "https://api.longcat.chat/openai/v1"
    
    SUPPORTED_MODELS = [
        "LongCat-2.0-Preview",
        "LongCat-Flash-Chat",
        "LongCat-Flash-Thinking",
    ]
    
    def __init__(
        self,
        api_key: str,
        model: str = "LongCat-2.0-Preview",
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 60,
        **kwargs,
    ):
        super().__init__(config=None)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or self.BASE_URL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._client = None
    
    async def initialize(self) -> None:
        """初始化 HTTP 客户端"""
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            self._initialized = True
            logger.info(f"LongCatAdapter initialized: {self.base_url}")
        except ImportError:
            raise ImportError("httpx is required for LongCat adapter. Install with: pip install httpx")
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
    
    async def chat(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> NormalizedResponse:
        """发送聊天请求到 LongCat API"""
        if not self._client:
            await self.initialize()
        
        all_messages = []
        
        if system_prompt:
            all_messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        for msg in messages:
            if isinstance(msg, Message):
                role = msg.role
                content = msg.content
            else:
                role = msg.get("role", "user")
                content = msg.get("content", "")
            
            if isinstance(content, list):
                text_content = ""
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_content += block.get("text", "")
                    elif hasattr(block, 'text'):
                        text_content += block.text
                content = text_content
            
            all_messages.append({
                "role": role,
                "content": str(content) if content else "",
            })
        
        request_data = {
            "model": self.model,
            "messages": all_messages,
        }
        
        temp = temperature if temperature is not None else self.temperature
        if temp:
            request_data["temperature"] = temp
        
        tokens = max_tokens if max_tokens else self.max_tokens
        if tokens:
            request_data["max_tokens"] = tokens
        
        if tools:
            request_data["tools"] = tools
            if tool_choice:
                request_data["tool_choice"] = tool_choice
        
        try:
            response = await self._client.post("/chat/completions", json=request_data)
            response.raise_for_status()
            data = response.json()
            
            return self._parse_response(data)
            
        except Exception as e:
            logger.error(f"LongCat API error: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> AsyncGenerator[NormalizedResponse, None]:
        """流式响应"""
        if not self._client:
            await self.initialize()
        
        all_messages = []
        
        if system_prompt:
            all_messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        for msg in messages:
            if isinstance(msg, Message):
                role = msg.role
                content = msg.content
            else:
                role = msg.get("role", "user")
                content = msg.get("content", "")
            
            if isinstance(content, list):
                content = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
            
            all_messages.append({
                "role": role,
                "content": str(content) if content else "",
            })
        
        request_data = {
            "model": self.model,
            "messages": all_messages,
            "stream": True,
        }
        
        if tools:
            request_data["tools"] = tools
        
        if self.temperature:
            request_data["temperature"] = self.temperature
        if self.max_tokens:
            request_data["max_tokens"] = self.max_tokens
        
        try:
            async with self._client.stream("POST", "/chat/completions", json=request_data) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield NormalizedResponse(content=content)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"LongCat stream error: {e}")
            raise
    
    def chat_sync(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> NormalizedResponse:
        """同步聊天"""
        return asyncio.get_event_loop().run_until_complete(
            self.chat(messages, system_prompt, tools, **kwargs)
        )
    
    def _parse_response(self, data: Dict[str, Any]) -> NormalizedResponse:
        """解析 API 响应"""
        choices = data.get("choices", [])
        
        if not choices:
            return NormalizedResponse(
                content="No response from model",
                tool_calls=[],
            )
        
        choice = choices[0]
        message = choice.get("message", {})
        
        content = message.get("content", "")
        
        tool_calls = []
        raw_tool_calls = message.get("tool_calls", [])
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            args_str = func.get("arguments", "{}")
            if isinstance(args_str, str):
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}
            else:
                args = args_str
            
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=func.get("name", ""),
                arguments=args,
            ))
        
        return NormalizedResponse(
            content=content,
            tool_calls=tool_calls if tool_calls else None,
            usage=data.get("usage", {}),
        )
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "LongCatAdapter":
        """从配置创建适配器"""
        return cls(
            api_key=config.get("api_key", ""),
            model=config.get("model", "LongCat-2.0-Preview"),
            base_url=config.get("base_url", cls.BASE_URL),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 4096),
        )
