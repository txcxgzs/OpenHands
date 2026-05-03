"""
AuroraAgent Package - AI Assistant with Windows Control
Deep reference from OpenClaw and Hermes Agent

Architecture:
- EmbeddedAgent: Core runtime (OpenClaw style)
- ToolRegistry: Tool management
- ToolPolicyManager: Permission and policy
- MemoryStore: Vector memory search
- Model Adapters: Multi-provider support
- SubAgentManager: Task delegation
- MCPClient: Protocol support
- ChannelManager: Channel integrations
- PluginManager: Extensibility
"""

__version__ = "0.1.0"

from .core import (
    AgentConfig,
    EmbeddedAgent,
    tool_registry,
    ToolPolicyManager,
    MemoryStore,
)
from .core.subagents import SubAgentManager, SubAgentConfig
from .core.mcp import MCPClient, MCPServer, MCPTool
from .channels import Channel, ChannelManager, ChannelMessage, ChannelConfig
from .plugins import Plugin, PluginManager, PluginMetadata

__all__ = [
    # Core
    "AgentConfig",
    "EmbeddedAgent",
    "tool_registry",
    "ToolPolicyManager",
    "MemoryStore",
    # Subagents
    "SubAgentManager",
    "SubAgentConfig",
    # MCP
    "MCPClient",
    "MCPServer",
    "MCPTool",
    # Channels
    "Channel",
    "ChannelManager",
    "ChannelMessage",
    "ChannelConfig",
    # Plugins
    "Plugin",
    "PluginManager",
    "PluginMetadata",
]
