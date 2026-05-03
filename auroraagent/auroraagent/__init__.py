
"""
AuroraAgent Main Package
"""

from .core import AuroraAgent, AgentConfig
from .core.agent.runner import EmbeddedAgent
from .core.tools.registry import tool_registry
from .core.tools.policy import ToolPolicyManager
from .core.memory.store import MemoryStore

__version__ = "0.1.0"

__all__ = [
    "AuroraAgent",
    "AgentConfig",
    "EmbeddedAgent",
    "tool_registry",
    "ToolPolicyManager",
    "MemoryStore",
]
