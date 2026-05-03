"""
OpenHands - AI Assistant with Windows Control
Deep reference from OpenClaw and Hermes Agent
"""

__version__ = "0.1.0"

# Core
from .core import AgentConfig, ModelConfig, MemoryConfig, ToolConfig, WindowsConfig
from .core.memory import MemoryStore, MemoryItem
from .core.tools import tool_registry, ToolRegistry, ToolResult
from .core.tools.policy import ToolPolicyManager
from .core.agent import EmbeddedAgent
from .core.loadbalancer import LoadBalancer, ModelFailover, ProviderConfig

# Adapters
from .core.adapters import (
    AnthropicAdapter,
    OpenAIAdapter,
    OpenRouterAdapter,
    get_adapter,
    list_providers,
)

# Channels
from .channels import (
    SlackChannel,
    DiscordChannel,
    TelegramChannel,
    WhatsAppChannel,
    TeamsChannel,
    FeishuChannel,
    ChannelManager,
    ChannelMessage,
)

# Automation
from .automation import WebhookManager, WebhookEvent, WebhookTool

# Monitoring
from .monitoring import MonitoringManager, PrometheusMetrics, OpenTelemetryExporter

# Memory
from .memory import MemorySystem

__all__ = [
    # Version
    "__version__",
    # Core
    "AgentConfig",
    "ModelConfig",
    "MemoryConfig",
    "ToolConfig",
    "WindowsConfig",
    "MemoryStore",
    "MemoryItem",
    "tool_registry",
    "ToolRegistry",
    "ToolResult",
    "ToolPolicyManager",
    "EmbeddedAgent",
    "LoadBalancer",
    "ModelFailover",
    "ProviderConfig",
    # Adapters
    "AnthropicAdapter",
    "OpenAIAdapter",
    "OpenRouterAdapter",
    "get_adapter",
    "list_providers",
    # Channels
    "SlackChannel",
    "DiscordChannel",
    "TelegramChannel",
    "WhatsAppChannel",
    "TeamsChannel",
    "FeishuChannel",
    "ChannelManager",
    "ChannelMessage",
    # Automation
    "WebhookManager",
    "WebhookEvent",
    "WebhookTool",
    # Monitoring
    "MonitoringManager",
    "PrometheusMetrics",
    "OpenTelemetryExporter",
    # Memory
    "MemorySystem",
]

# Alias for backwards compatibility
Agent = EmbeddedAgent
OpenHands = EmbeddedAgent
