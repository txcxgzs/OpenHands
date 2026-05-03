
"""
Adapters Package
"""
from .base import ModelAdapter, NormalizedResponse, Message, ToolCall, ToolResult
from .anthropic_adapter import AnthropicAdapter
from .openai_adapter import OpenAIAdapter

_ADAPTERS = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
}


def get_adapter_class(provider: str):
    """Get adapter class for provider"""
    return _ADAPTERS.get(provider.lower())


def register_adapter(provider: str, adapter_class):
    """Register adapter"""
    _ADAPTERS[provider.lower()] = adapter_class


def list_adapters():
    """List available adapters"""
    return list(_ADAPTERS.keys())


__all__ = [
    "ModelAdapter",
    "NormalizedResponse",
    "Message",
    "ToolCall",
    "ToolResult",
    "AnthropicAdapter",
    "OpenAIAdapter",
    "get_adapter_class",
    "register_adapter",
    "list_adapters",
]
