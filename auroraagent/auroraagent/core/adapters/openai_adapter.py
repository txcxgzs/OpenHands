from typing import List, Dict, Any, Optional, AsyncGenerator
from .base import ModelAdapter, NormalizedResponse, Message, ToolCall, ToolResult
from ..config import ModelConfig
import os
import json


class OpenAIAdapter(ModelAdapter):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._client = None
        self._async_client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                api_key = self._config.api_key or os.getenv("OPENAI_API_KEY")
                base_url = self._config.base_url or os.getenv("OPENAI_BASE_URL")
                self._client = OpenAI(
                    api_key=api_key,
                    base_url=base_url
                )
            except ImportError:
                raise ImportError("openai package not installed")
        return self._client

    def _get_async_client(self):
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
                api_key = self._config.api_key or os.getenv("OPENAI_API_KEY")
                base_url = self._config.base_url or os.getenv("OPENAI_BASE_URL")
                self._async_client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url
                )
            except ImportError:
                raise ImportError("openai package not installed")
        return self._async_client

    def _convert_to_openai_messages(self, messages: List[Message]) -> List[Dict]:
        result = []
        for msg in messages:
            openai_msg = {"role": msg.role}
            if isinstance(msg.content, str):
                openai_msg["content"] = msg.content
            else:
                openai_msg["content"] = msg.content
            if msg.tool_calls:
                openai_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id
            result.append(openai_msg)
        return result

    def _convert_from_openai_tool_calls(self, tool_calls: Any) -> List[ToolCall]:
        if not tool_calls:
            return []
        result = []
        for tc in tool_calls:
            try:
                arguments = json.loads(tc.function.arguments)
            except Exception:
                arguments = {}
            result.append(ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=arguments
            ))
        return result

    async def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> NormalizedResponse:
        client = self._get_async_client()
        openai_messages = self._convert_to_openai_messages(messages)

        openai_tools = None
        if tools:
            openai_tools = [
                {"type": "function", ,"function": tool}
                for tool in tools
            ]

        params = {
            "model": self._config.model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self._config.temperature),
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
        }

        if openai_tools:
            params["tools"] = openai_tools

        response = await client.chat.completions.create(**params)
        choice = response.choices[0]

        return NormalizedResponse(
            content=choice.message.content,
            tool_calls=self._convert_from_openai_tool_calls(choice.message.tool_calls),
            raw_response=response,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None
        )

    async def chat_stream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncGenerator[NormalizedResponse, None]:
        client = self._get_async_client()
        openai_messages = self._convert_to_openai_messages(messages)

        openai_tools = None
        if tools:
            openai_tools = [
                {"type": "function", ,"function": tool}
                for tool in tools
            ]

        params = {
            "model": self._config.model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self._config.temperature),
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
            "stream": True
        }

        if openai_tools:
            params["tools"] = openai_tools

        stream = await client.chat.completions.create(**params)
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                yield NormalizedResponse(
                    content=delta.content,
                    tool_calls=self._convert_from_openai_tool_calls(delta.tool_calls),
                    raw_response=chunk
                )

    def chat_sync(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> NormalizedResponse:
        client = self._get_client()
        openai_messages = self._convert_to_openai_messages(messages)

        openai_tools = None
        if tools:
            openai_tools = [
                {"type": "function" ,"function": tool}
                for tool in tools
            ]

        params = {
            "model": self._config.model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self._config.temperature),
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
        }

        if openai_tools:
            params["tools"] = openai_tools

        response = client.chat.completions.create(**params)
        choice = response.choices[0]

        return NormalizedResponse(
            content=choice.message.content,
            tool_calls=self._convert_from_openai_tool_calls(choice.message.tool_calls),
            raw_response=response,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None
        )
