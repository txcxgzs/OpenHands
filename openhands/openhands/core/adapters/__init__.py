"""
Model Adapters Package
"""
from .base import ModelAdapter
from .anthropic_adapter import AnthropicAdapter
from .openai_adapter import OpenAIAdapter
from .openrouter_adapter import OpenRouterAdapter
from .extra_adapters import (
    OllamaAdapter,
    GroqAdapter,
    TogetherAIAdapter,
    DeepSeekAdapter,
    MistralAdapter,
    ADAPTERS,
    get_adapter,
    list_providers,
)

# 向后兼容
ADAPTER_MAP = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
    "openrouter": OpenRouterAdapter,
    "ollama": OllamaAdapter,
    "groq": GroqAdapter,
    "together": TogetherAIAdapter,
    "deepseek": DeepSeekAdapter,
    "mistral": MistralAdapter,
}


def get_adapter_class(provider: str):
    """获取适配器类"""
    return ADAPTER_MAP.get(provider.lower())


__all__ = [
    "ModelAdapter",
    "AnthropicAdapter",
    "OpenAIAdapter",
    "OpenRouterAdapter",
    "OllamaAdapter",
    "GroqAdapter",
    "TogetherAIAdapter",
    "DeepSeekAdapter",
    "MistralAdapter",
    "ADAPTERS",
    "get_adapter",
    "list_providers",
    "get_adapter_class",
]
