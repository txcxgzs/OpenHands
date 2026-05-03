"""
LongCat API Adapter
支持 LongCat-2.0-Preview模型
API: https://api.longcat.chat/openai/v1
"""

from typing import Dict, List, Optional, Any, AsyncGenerator
import json
import logging
import asyncio
import os

logger = logging.getLogger(__name__)


class LongCatAdapter:
    """
    LongCat AI模型适配器
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
    
    def __init__(self, config):
        self.config = config
        self.api_key = getattr(config, 'api_key', None)
        self.model = getattr(config, 'model', "LongCat-2.0-Preview")
        self.base_url = getattr(config, 'base_url', self.BASE_URL) or self.BASE_URL
        self.temperature = getattr(config, 'temperature', 0.7)
        self.max_tokens = getattr(config, 'max_tokens', 4096)
        self.timeout = getattr(config, 'timeout', 60)
        self._client = None
        self._initialized = False
    
    async def initialize(self):
        """初始化HTTP客户端"""
        if self._initialized:
            return
        
        try:
            import httpx
            
            if not self.api_key:
                self.api_key = os.getenv("LONGCAT_API_KEY", "")
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            self._initialized = True
            logger.info(f"LongCatAdapter初始化成功: {self.base_url}")
        except ImportError:
            raise ImportError("需要httpx库。请安装: pip install httpx")
    
    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
    
    async def chat(
        self,
        messages: List[Any],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ):
        """发送聊天请求到LongCat API"""
        if not self._client:
            await self.initialize()
        
        all_messages = []
        
        if system_prompt:
            all_messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        for msg in messages:
            role, content = self._extract_msg_role_content(msg)
            all_messages.append({
                "role": role,
                "content": self._normalize_content(content),
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
        
        # 暂时不支持工具调用 - 可能会导致API错误
        # if tools:
        #     request_data["tools"] = tools
        #     if "tool_choice" in kwargs:
        #         request_data["tool_choice"] = kwargs["tool_choice"]
        
        try:
            response = await self._client.post("/chat/completions", json=request_data)
            response.raise_for_status()
            text = response.text
            
            try:
                data = json.loads(text)
                return self._parse_response(data)
            except json.JSONDecodeError as e:
                logger.error(f"LongCat API JSON解析错误: {e}")
                logger.error(f"响应文本: {text}")
                return self._create_simple_response(text[:500] if text else "收到空响应")
            
        except Exception as e:
            logger.error(f"LongCat API错误: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[Any],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[Any, None]:
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
            role, content = self._extract_msg_role_content(msg)
            all_messages.append({
                "role": role,
                "content": self._normalize_content(content),
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
                                yield self._create_simple_response(content)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"LongCat流式错误: {e}")
            raise
    
    def chat_sync(
        self,
        messages: List[Any],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ):
        """同步聊天"""
        return asyncio.get_event_loop().run_until_complete(
            self.chat(messages, tools, system_prompt, **kwargs)
        )
    
    def _extract_msg_role_content(self, msg):
        """提取角色和内容"""
        if hasattr(msg, 'role') and hasattr(msg, 'content'):
            role = getattr(msg, 'role', 'user')
            content = getattr(msg, 'content', '')
            if hasattr(role, 'value'):
                role = role.value
            return role, content
        elif isinstance(msg, dict):
            return msg.get('role', 'user'), msg.get('content', '')
        return 'user', str(msg)
    
    def _normalize_content(self, content):
        """规范化内容"""
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                elif hasattr(block, 'text'):
                    text_parts.append(getattr(block, 'text', ''))
                else:
                    text_parts.append(str(block))
            return '\n'.join(text_parts)
        return str(content) if content is not None else ''
    
    def _parse_response(self, data):
        """解析API响应"""
        choices = data.get("choices", [])
        
        if not choices:
            return self._create_simple_response("未收到模型响应")
        
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
            tool_calls.append({
                "id": tc.get("id", ""),
                "name": func.get("name", ""),
                "arguments": args
            })
        
        return self._create_simple_response(content, tool_calls if tool_calls else None, data.get("usage"))
    
    def _create_simple_response(self, content, tool_calls=None, usage=None):
        """创建简单响应对象"""
        class SimpleResponse:
            def __init__(self, content, tool_calls, usage):
                self.content = content
                self.tool_calls = tool_calls
                self.usage = usage or {}
        return SimpleResponse(content, tool_calls, usage)
    
    @classmethod
    def from_config(cls, config):
        """从配置创建适配器"""
        return cls(config)
