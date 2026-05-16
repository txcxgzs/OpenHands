"""
Tests for adapters
"""

import pytest
from openhands import AgentConfig
from openhands.adapters import get_adapter_class, list_adapters


def test_list_adapters():
    """Test listing adapters"""
    adapters = list_adapters()
    assert "anthropic" in adapters
    assert "openai" in adapters


def test_get_adapter_class():
    """Test getting adapter class"""
    cls = get_adapter_class("anthropic")
    assert cls is not None

    cls = get_adapter_class("openai")
    assert cls is not None

    cls = get_adapter_class("unknown")
    assert cls is None


@pytest.mark.asyncio
async def test_adapter_initialization():
    """Test adapter initialization"""
    config = AgentConfig()
    config.model.provider = "anthropic"

    cls = get_adapter_class(config.model.provider)
    adapter = cls(config.model)

    # Just test it can be created, don't actually init (requires API key)
    assert adapter is not None
