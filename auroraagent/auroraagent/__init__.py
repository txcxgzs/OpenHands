"""
AuroraAgent - AI Assistant with Windows Control
"""

__version__ = "0.1.0"

# Safe default imports
from .core.config import AgentConfig
from .tools.registry import tool_registry, ToolRegistry, ToolResult
from .core.tools.policy import ToolPolicyManager
from .core.memory.store import MemoryStore

__all__ = [
    "AgentConfig",
    "tool_registry",
    "ToolRegistry",
    "ToolResult",
    "ToolPolicyManager",
    "MemoryStore",
]
