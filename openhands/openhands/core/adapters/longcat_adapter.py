"""
LongCat API Adapter
支持 LongCat-2.0-Preview模型
API: https://api.longcat.chat/openai/v1
"""

from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass
import json
import logging
import asyncio
import os

logger = logging.getLogger(__name__)


@dataclass
class LongCatToolCall:
    """Tool call from LongCat"""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LongCatResponse:
    """Response from LongCat"""
    content: Optional[str] = None
    tool_calls: Optional[List[LongCatToolCall]] = None


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
        self.max_tokens = getattr(config, 'max_tokens', 8192)
        self.timeout = getattr(config, 'timeout', 120)
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
    
    def _extract_msg_role_content(self, msg):
        """提取消息角色和内容"""
        if hasattr(msg, 'role') and hasattr(msg, 'content'):
            return msg.role.value, msg.content
        elif isinstance(msg, dict):
            return msg.get('role', 'user'), msg.get('content', '')
        else:
            return 'user', str(msg)
    
    def _normalize_content(self, content):
        """规范化内容"""
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    parts.append(part.get('text', ''))
            return '\n'.join(parts)
        return content
    
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
        
        if tools and len(tools) > 0:
            request_data["tools"] = tools
            logger.debug(f"发送工具定义给模型: {[t['name'] for t in tools]}")
            if "tool_choice" in kwargs:
                request_data["tool_choice"] = kwargs["tool_choice"]
        
        try:
            logger.debug(f"发送请求到LongCat API")
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
            "stream_options": {"include_usage": True},
        }
        
        if tools and len(tools) > 0:
            request_data["tools"] = tools
            logger.debug(f"流式发送工具定义给模型: {[t['name'] for t in tools]}")
        
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
                            choices = data.get("choices", [])
                            if not choices:
                                continue
                            
                            delta = choices[0].get("delta", {})
                            
                            # 先看有没有工具调用
                            tool_calls = delta.get("tool_calls", [])
                            if tool_calls and len(tool_calls) > 0:
                                yield self._parse_tool_delta(data)
                            else:
                                # 普通文本
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
        **kwargs,
    ):
        """同步聊天"""
        return asyncio.run(self.chat(messages, tools, **kwargs))
    
    def _parse_response(self, data):
        """解析LongCat API响应"""
        try:
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            content = message.get("content")
            tool_calls_data = message.get("tool_calls", [])
            
            tool_calls = []
            if tool_calls_data:
                for tc in tool_calls_data:
                    tc_id = tc.get("id", "")
                    tc_func = tc.get("function", {})
                    tc_name = tc_func.get("name", "")
                    tc_args = tc_func.get("arguments", "{}")
                    try:
                        args = json.loads(tc_args)
                    except json.JSONDecodeError:
                        args = {"raw": tc_args}
                    tool_calls.append(LongCatToolCall(id=tc_id, name=tc_name, arguments=args))
                    logger.debug(f"解析到工具调用: {tc_name}")
            
            result = LongCatResponse(content=content, tool_calls=tool_calls)
            return result
        except Exception as e:
            logger.error(f"解析LongCat响应错误: {e}")
            return self._create_simple_response("解析响应错误")
    
    def _parse_tool_delta(self, data):
        """解析工具调用delta"""
        choice = data.get("choices", [{}])[0]
        delta = choice.get("delta", {})
        
        tool_calls = delta.get("tool_calls", [])
        if not tool_calls:
            return self._create_simple_response("")
        
        result = []
        for tc in tool_calls:
            tc_func = tc.get("function", {})
            tc_name = tc_func.get("name", "")
            tc_args_str = tc_func.get("arguments", "")
            
            try:
                if tc_args_str:
                    args = json.loads(tc_args_str)
                else:
                    args = {}
            except json.JSONDecodeError:
                args = {"raw": tc_args_str}
            
            tc_id = tc.get("id", f"tool-{id(tc)}")
            result.append(LongCatToolCall(id=tc_id, name=tc_name, arguments=args))
        
        return LongCatResponse(content=None, tool_calls=result)
    
    def _create_simple_response(self, content):
        """创建简单响应"""
        return LongCatResponse(content=content, tool_calls=None)


# 导出兼容类名
ModelAdapter = LongCatAdapter
