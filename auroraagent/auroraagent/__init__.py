"""
AuroraAgent - AI Assistant with Windows Control
"""

__version__ = "0.1.0"

from auroraagent.core.agent import EmbeddedAgent
from auroraagent.core.config import AgentConfig
from auroraagent.core.memory.store import MemoryStore
from auroraagent.core.tools.registry import tool_registry
from auroraagent.core.tools.policy import ToolPolicyManager

__all__ = [
    "AgentConfig",
    "EmbeddedAgent",
    "MemoryStore",
    "tool_registry",
    "ToolPolicyManager",
]
