
"""
Anthropic Claude Model Adapter
References OpenClaw's Claude integration
"""

import base64
import os
from typing import Any, Dict, List, Optional, AsyncGenerator
import logging
import asyncio

from .base import ModelAdapter, NormalizedResponse, Message, ToolCall

logger = logging.getLogger(__name__)


class AnthropicAdapter(ModelAdapter):
    """Anthropic Claude Adapter"""

    def __init__(self, config):
        super().__init__(config)
        self._client = None
        self._async_client = None

    async def initialize(self):
        """Initialize Anthropic clients"""
        if self._initialized:
            return

        from anthropic import Anthropic, AsyncAnthropic

        api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
        base_url = self.config.base_url or os.getenv("ANTHROPIC_BASE_URL")

        self._client = Anthropic(
            api_key=api_key,
            base_url=base_url,
        )
        self._async_client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
        )

        self._initialized = True
        logger.info("Anthropic adapter initialized")

    async def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> NormalizedResponse:
        """Chat with Claude"""
        anthropic_system, anthropic_messages = self._convert_messages(
            messages, system_prompt
        )
        anthropic_tools = self._convert_tools(tools)

        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        temperature = kwargs.get("temperature", self.config.temperature)

        response = await self._async_client.messages.create(
            model=self.config.model,
            system=anthropic_system,
            messages=anthropic_messages,
            tools=anthropic_tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return self._normalize_response(response)

    async def chat_stream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[NormalizedResponse, None]:
        """Stream chat with Claude"""
        anthropic_system, anthropic_messages = self._convert_messages(
            messages, system_prompt
        )
        anthropic_tools = self._convert_tools(tools)

        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        temperature = kwargs.get("temperature", self.config.temperature)

        stream = await self._async_client.messages.create(
            model=self.config.model,
            system=anthropic_system,
            messages=anthropic_messages,
            tools=anthropic_tools,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

        async for event in stream:
            yield self._normalize_event_to_response(event)

    def chat_sync(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> NormalizedResponse:
        """Synchronous chat with Claude"""
        anthropic_system, anthropic_messages = self._convert_messages(
            messages, system_prompt
        )
        anthropic_tools = self._convert_tools(tools)

        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        temperature = kwargs.get("temperature", self.config.temperature)

        response = self._client.messages.create(
            model=self.config.model,
            system=anthropic_system,
            messages=anthropic_messages,
            tools=anthropic_tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return self._normalize_response(response)

    def _convert_messages(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> tuple[Optional[str], List[Dict]]:
        """Convert messages to Anthropic format"""
        anthropic_messages = []

        for msg in messages:
            role = msg.role
            content = msg.content

            if role == "system":
                system_prompt = str(content) if content else system_prompt
                continue

            anthropic_msg = self._convert_single_message(msg)
            anthropic_messages.append(anthropic_msg)

        return system_prompt, anthropic_messages

    def _convert_single_message(self, msg: Message) -> Dict:
        """Convert single message to Anthropic format"""
        role = msg.role
        content = msg.content

        if isinstance(content, list):
            processed_content = []
            for part in content:
                if hasattr(part, "type"):
                    if part.type == "image":
                        processed_content.append(part.__dict__)
                    elif part.type == "text":
                        processed_content.append({"type": "text", "text": part.text})
                elif isinstance(part, dict):
                    processed_content.append(part)
                else:
                    processed_content.append({"type": "text", "text": str(part)})
            content = processed_content
        elif content is not None:
            content = str(content)

        if role == "assistant" and msg.tool_calls:
            content_list = []
            if content:
                content_list.append({"type": "text", "text": str(content)})
            content_list.extend(self._convert_tool_calls(msg.tool_calls))
            content = content_list

        return {"role": role, "content": content}

    def _convert_image(self, image_data: Dict) -> Dict:
        """Convert image data"""
        source = image_data.get("source", {})
        media_type = source.get("media_type", "image/png")
        data = source.get("data")

        if data and not data.startswith("data:"):
            data = data.split(",", 1)[1]

        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data,
            },
        }

    def _convert_tool_calls(self, tool_calls: List[ToolCall]) -> List[Dict]:
        """Convert tool calls to Anthropic format"""
        return [
            {
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            }
            for tc in tool_calls
        ]

    def _convert_tools(self, tools: Optional[List[Dict]]) -> Optional[List[Dict]]:
        """Convert tools to Anthropic format"""
        if not tools:
            return None

        converted = []
        for tool in tools:
            if tool.get("type") == "function":
                fn = tool.get("function", {})
                converted.append({
                    "name": fn.get("name", tool.get("name", "")),
                    "description": fn.get("description", tool.get("description", "")),
                    "input_schema": fn.get("parameters", tool.get("parameters", {})),
                })
            else:
                converted.append({
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters", {}),
                })
        return converted

    def _normalize_response(self, response) -> NormalizedResponse:
        """Normalize response to our format"""
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        usage = None
        if hasattr(response, "usage"):
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

        return NormalizedResponse(
            content=content if content else None,
            tool_calls=tool_calls if tool_calls else None,
            raw_response=response,
            usage=usage,
        )

    def _normalize_event_to_response(self, event) -> NormalizedResponse:
        """Normalize streaming event to response"""
        content = None
        tool_calls = None

        if hasattr(event, "type"):
            if event.type == "content_block_delta" and hasattr(event, "delta"):
                if hasattr(event.delta, "text"):
                    content = event.delta.text

        return NormalizedResponse(
            content=content,
            tool_calls=tool_calls,
            raw_response=event,
        )
