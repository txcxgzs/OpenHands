"""
OpenHands - AI Assistant with Windows Control
Deep reference from OpenClaw and Hermes Agent
With Self-Improving Capabilities
"""

__version__ = "0.2.0"

# Core
from .core import AgentConfig, ModelConfig, MemoryConfig, ToolConfig, WindowsConfig
from .core.memory import MemoryStore, MemoryItem
from .core.tools import tool_registry, ToolRegistry, ToolResult
from .core.tools.policy import ToolPolicyManager
from .core.agent import EmbeddedAgent
from .core.loadbalancer import LoadBalancer, ModelFailover, ProviderConfig

# Core - Hermes-style innovations
from .core.budget import IterationBudget, BudgetManager, budget_manager
from .core.parallel import (
    ParallelToolExecutor,
    parallel_executor,
    ToolCall,
    NEVER_PARALLEL_TOOLS,
    PARALLEL_SAFE_TOOLS,
    PATH_SCOPED_TOOLS,
)
from .core.security import (
    SecurityScanner,
    security_scanner,
    ThreatPattern,
    ScanResult,
    Severity,
    TrustLevel,
)
from .core.fuzzy_match import FuzzyMatcher, fuzzy_matcher, fuzzy_find_and_replace

# Adapters
from .core.adapters import (
    AnthropicAdapter,
    OpenAIAdapter,
    OpenRouterAdapter,
    LongCatAdapter,
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

# Self-Improving (Hermes-style)
from .skills import (
    SkillManager,
    Skill,
    skill_manager,
    NudgeEngine,
    NudgeConfig,
    ReviewAgent,
    EnhancedMemoryStore,
    MEMORY_GUIDANCE,
)

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
    # Core - Hermes-style innovations
    "IterationBudget",
    "BudgetManager",
    "budget_manager",
    "ParallelToolExecutor",
    "parallel_executor",
    "ToolCall",
    "NEVER_PARALLEL_TOOLS",
    "PARALLEL_SAFE_TOOLS",
    "PATH_SCOPED_TOOLS",
    "SecurityScanner",
    "security_scanner",
    "ThreatPattern",
    "ScanResult",
    "Severity",
    "TrustLevel",
    "FuzzyMatcher",
    "fuzzy_matcher",
    "fuzzy_find_and_replace",
    # Adapters
    "AnthropicAdapter",
    "OpenAIAdapter",
    "OpenRouterAdapter",
    "LongCatAdapter",
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
    # Self-Improving
    "SkillManager",
    "Skill",
    "skill_manager",
    "NudgeEngine",
    "NudgeConfig",
    "ReviewAgent",
    "EnhancedMemoryStore",
    "MEMORY_GUIDANCE",
]

# Alias for backwards compatibility
Agent = EmbeddedAgent
OpenHands = EmbeddedAgent
