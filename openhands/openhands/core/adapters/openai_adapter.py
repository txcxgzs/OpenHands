
"""
OpenAI Model Adapter
"""

import os
import json
from typing import Any, Dict, List, Optional, AsyncGenerator
import logging

from .base import ModelAdapter, NormalizedResponse, Message, ToolCall

logger = logging.getLogger(__name__)


class OpenAIAdapter(ModelAdapter):
    """OpenAI Adapter"""

    def __init__(self, config):
        super().__init__(config)
        self._client = None
        self._async_client = None

    async def initialize(self):
        if self._initialized:
            return

        from openai import OpenAI, AsyncOpenAI

        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        base_url = self.config.base_url or os.getenv("OPENAI_BASE_URL")

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._initialized = True

    async def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> NormalizedResponse:
        openai_messages = self._convert_messages(messages, system_prompt)
        openai_tools = self._convert_tools(tools)

        response = await self._async_client.chat.completions.create(
            model=self.config.model,
            messages=openai_messages,
            tools=openai_tools,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
        )

        return self._normalize_response(response)

    async def chat_stream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[NormalizedResponse, None]:
        openai_messages = self._convert_messages(messages, system_prompt)
        openai_tools = self._convert_tools(tools)

        stream = await self._async_client.chat.completions.create(
            model=self.config.model,
            messages=openai_messages,
            tools=openai_tools,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            stream=True,
        )

        async for chunk in stream:
            yield self._normalize_chunk(chunk)

    def chat_sync(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> NormalizedResponse:
        openai_messages = self._convert_messages(messages, system_prompt)
        openai_tools = self._convert_tools(tools)

        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=openai_messages,
            tools=openai_tools,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
        )

        return self._normalize_response(response)

    def _convert_messages(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> List[Dict]:
        result = []
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        for msg in messages:
            openai_msg = {"role": msg.role}
            if isinstance(msg.content, str):
                openai_msg["content"] = msg.content
            elif isinstance(msg.content, list):
                openai_msg["content"] = msg.content
            else:
                openai_msg["content"] = str(msg.content) if msg.content else ""

            if msg.tool_calls:
                openai_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]

            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id

            result.append(openai_msg)
        return result

    def _convert_tools(self, tools: Optional[List[Dict]]) -> Optional[List[Dict]]:
        if not tools:
            return None

        return [
            {
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", t.get("input_schema", {})),
                },
            }
            for t in tools
        ]

    def _normalize_response(self, response) -> NormalizedResponse:
        choice = response.choices[0]
        content = choice.message.content

        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                )
                for tc in choice.message.tool_calls
            ]

        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return NormalizedResponse(
            content=content,
            tool_calls=tool_calls,
            raw_response=response,
            usage=usage,
        )

    def _normalize_chunk(self, chunk) -> NormalizedResponse:
        content = None
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
        return NormalizedResponse(content=content, raw_response=chunk)
