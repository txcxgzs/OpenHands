"""
AuroraAgent - Windows 原生 AI Agent
深度参考 OpenClaw 和 Hermes Agent 的架构设计
"""

__version__ = "0.1.0"
__author__ = "Aurora Team"

from .core.agent import AuroraAgent
from .core.config import AgentConfig

__all__ = ["AuroraAgent", "AgentConfig"]
