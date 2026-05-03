"""
Skills Package - Self-improving skill system
Reference: Hermes Agent's self-evolution mechanism
"""

from .skill_manager import SkillManager, Skill, SkillMetadata, skill_manager
from .nudge_engine import NudgeEngine, NudgeConfig, NudgeState
from .review_agent import ReviewAgent, ReviewResult, run_background_review
from .enhanced_memory import (
    EnhancedMemoryStore,
    MemoryEntry,
    MEMORY_LIMIT,
    USER_MEMORY_LIMIT,
    MEMORY_GUIDANCE,
)

__all__ = [
    # Skill System
    "SkillManager",
    "Skill",
    "SkillMetadata",
    "skill_manager",
    # Nudge Engine
    "NudgeEngine",
    "NudgeConfig",
    "NudgeState",
    # Review Agent
    "ReviewAgent",
    "ReviewResult",
    "run_background_review",
    # Enhanced Memory
    "EnhancedMemoryStore",
    "MemoryEntry",
    "MEMORY_LIMIT",
    "USER_MEMORY_LIMIT",
    "MEMORY_GUIDANCE",
]
