from .base import ModelAdapter, NormalizedResponse, Message, ToolCall, ToolResult
from .anthropic_adapter import AnthropicAdapter
from .openai_adapter import OpenAIAdapter

__all__ = [
    "ModelAdapter",
    "NormalizedResponse",
    "Message",
    "ToolCall",
    "ToolResult",
    "AnthropicAdapter",
    "OpenAIAdapter",
]

_ADAPTERS = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
}


def get_adapter_class(provider: str):
    return _ADAPTERS.get(provider.lower())


def register_adapter(provider: str, adapter_class):
    _ADAPTERS[provider.lower()] = adapter_class


def list_adapters():
    return list(_ADAPTERS.keys())
