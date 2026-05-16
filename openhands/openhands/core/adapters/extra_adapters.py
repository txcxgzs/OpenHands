"""
更多模型提供商适配器
"""

from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass
import logging
import json

logger = logging.getLogger(__name__)


class OllamaAdapter:
    """Ollama 本地模型适配器"""

    def __init__(self, config):
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "llama2")
        self._client = None

    async def initialize(self):
        import httpx
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120)
        logger.info(f"Ollama adapter initialized: {self.base_url}")

    async def chat(self, messages: List[Dict], **kwargs) -> Dict:
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

        async with self._client as client:
            response = await client.post("/api/generate", json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            })

        return {
            "content": response.json().get("response", ""),
            "raw_response": response.json(),
        }

    async def chat_stream(self, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

        async with self._client as client:
            async with client.stream("/api/generate", json={
                "model": self.model,
                "prompt": prompt,
                "stream": True,
            }) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        yield data.get("response", "")


class GroqAdapter:
    """Groq API 适配器"""

    def __init__(self, config):
        self.api_key = config.get("api_key")
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = config.get("model", "mixtral-8x7b-32768")
        self._client = None

    async def initialize(self):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.info("Groq adapter initialized")

    async def chat(self, messages: List[Dict], **kwargs) -> Dict:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def chat_stream(self, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class TogetherAIAdapter:
    """Together AI 适配器"""

    def __init__(self, config):
        self.api_key = config.get("api_key")
        self.base_url = "https://api.together.xyz/v1"
        self.model = config.get("model", "meta-llama/Llama-3-70b-chat-hf")
        self._client = None

    async def initialize(self):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.info("TogetherAI adapter initialized")

    async def chat(self, messages: List[Dict], **kwargs) -> Dict:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def chat_stream(self, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class DeepSeekAdapter:
    """DeepSeek API 适配器"""

    def __init__(self, config):
        self.api_key = config.get("api_key")
        self.base_url = "https://api.deepseek.com/v1"
        self.model = config.get("model", "deepseek-chat")
        self._client = None

    async def initialize(self):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.info("DeepSeek adapter initialized")

    async def chat(self, messages: List[Dict], **kwargs) -> Dict:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def chat_stream(self, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class MistralAdapter:
    """Mistral AI 适配器"""

    def __init__(self, config):
        self.api_key = config.get("api_key")
        self.base_url = "https://api.mistral.ai/v1"
        self.model = config.get("model", "mistral-large-latest")
        self._client = None

    async def initialize(self):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.info("Mistral adapter initialized")

    async def chat(self, messages: List[Dict], **kwargs) -> Dict:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def chat_stream(self, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# 模型提供商映射
ADAPTERS = {
    "ollama": OllamaAdapter,
    "groq": GroqAdapter,
    "together": TogetherAIAdapter,
    "deepseek": DeepSeekAdapter,
    "mistral": MistralAdapter,
}


def get_adapter(provider: str):
    """获取适配器"""
    return ADAPTERS.get(provider.lower())


def list_providers() -> List[str]:
    """列出所有支持的提供商"""
    return list(ADAPTERS.keys())
