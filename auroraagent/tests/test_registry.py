"""
Tests for tool registry
"""

import pytest
from auroraagent import tool_registry


def test_registry_singleton():
    """Test registry is singleton"""
    reg1 = tool_registry()
    reg2 = tool_registry()
    assert reg1 is reg2


def test_registry_tools():
    """Test registry has tools"""
    registry = tool_registry()
    tools = registry.list_tools()
    assert len(tools) > 0


def test_tool_definitions():
    """Test tool definitions format"""
    registry = tool_registry()
    definitions = registry.get_definitions()

    assert len(definitions) > 0

    for defn in definitions:
        assert "name" in defn
        assert "description" in defn
        assert "input_schema" in defn
