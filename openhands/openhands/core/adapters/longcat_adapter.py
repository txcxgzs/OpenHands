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


def convert_tools_to_openai_format(tools: List[Dict]) -> List[Dict]:
    """转换工具定义为 OpenAI 格式"""
    openai_tools = []
    for tool in tools:
        if "type" in tool and tool["type"] == "function":
            openai_tools.append(tool)
        elif "function" in tool:
            openai_tools.append(tool)
        else:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", "unnamed"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", tool.get("parameters", {"type": "object", "properties": {}}))
                }
            })
    return openai_tools


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
            request_data["tools"] = convert_tools_to_openai_format(tools)
            tool_names = [t.get('function', {}).get('name', t.get('name', 'unknown')) for t in tools]
            logger.info(f"发送工具定义给模型: {tool_names}")
            if "tool_choice" in kwargs:
                request_data["tool_choice"] = kwargs["tool_choice"]
        
        try:
            logger.info(f"发送请求到LongCat API")
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
        """流式响应 - 正确处理工具调用"""
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
        
        if tools and len(tools) > 0:
            openai_tools = convert_tools_to_openai_format(tools)
            request_data["tools"] = openai_tools
            tool_names = [t.get('function', {}).get('name', t.get('name', 'unknown')) for t in openai_tools]
            logger.info(f"流式发送工具定义给模型: {tool_names}")
        
        if self.temperature:
            request_data["temperature"] = self.temperature
        if self.max_tokens:
            request_data["max_tokens"] = self.max_tokens
        
        try:
            accumulated_content = ""
            pending_tool_call = None
            pending_tool_id = None
            pending_tool_name = None
            
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
                            
                            choice = choices[0]
                            delta = choice.get("delta", {})
                            finish_reason = choice.get("finish_reason")
                            
                            if finish_reason == "tool_calls":
                                if pending_tool_call:
                                    logger.info(f"发送工具调用: {pending_tool_name} - {pending_tool_call}")
                                    yield LongCatResponse(content=None, tool_calls=[pending_tool_call])
                                pending_tool_call = None
                                pending_tool_id = None
                                pending_tool_name = None
                            elif finish_reason == "stop":
                                if accumulated_content:
                                    yield self._create_simple_response(accumulated_content)
                            else:
                                content = delta.get("content", "")
                                if content:
                                    accumulated_content += content
                                    yield self._create_simple_response(content)
                                
                                tool_calls_delta = delta.get("tool_calls", [])
                                for tc_delta in tool_calls_delta:
                                    func_delta = tc_delta.get("function", {})
                                    tc_id = tc_delta.get("id")
                                    tc_name = func_delta.get("name")
                                    tc_args_str = func_delta.get("arguments", "")
                                    
                                    if tc_id and tc_name:
                                        pending_tool_id = tc_id
                                        pending_tool_name = tc_name
                                        pending_tool_call = None
                                        accumulated_args_str = ""
                                    
                                    if pending_tool_name and tc_args_str:
                                        accumulated_args_str += tc_args_str
                                        try:
                                            pending_tool_call = LongCatToolCall(
                                                id=pending_tool_id or f"tool-{id(pending_tool_name)}",
                                                name=pending_tool_name,
                                                arguments=json.loads(accumulated_args_str)
                                            )
                                        except json.JSONDecodeError:
                                            pending_tool_call = LongCatToolCall(
                                                id=pending_tool_id or f"tool-{id(pending_tool_name)}",
                                                name=pending_tool_name,
                                                arguments={"raw": accumulated_args_str}
                                            )
                                    
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"LongCat流式错误: {e}")
            import traceback
            traceback.print_exc()
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
                    logger.info(f"解析到工具调用: {tc_name} - {args}")
            
            result = LongCatResponse(content=content, tool_calls=tool_calls)
            return result
        except Exception as e:
            logger.error(f"解析LongCat响应错误: {e}")
            import traceback
            traceback.print_exc()
            return self._create_simple_response("解析响应错误")
    
    def _create_simple_response(self, content):
        """创建简单响应"""
        return LongCatResponse(content=content, tool_calls=None)


ModelAdapter = LongCatAdapter
