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
from .curator import Curator, CuratorConfig, CuratorState, SkillState, curator
from .hindsight import (
    HindsightReplay,
    Trajectory,
    TrajectoryStep,
    AntiPattern,
    FailureType,
    hindsight_replay,
)
from .compression import (
    ExperienceCompressor,
    RawTrajectory,
    EpisodicMemory,
    ProceduralSkill,
    DeclarativeRule,
    CompressionLevel,
    experience_compressor,
)
from .utility_refiner import (
    MemoryRefiner,
    UtilityScorer,
    MemoryEntry as UtilityMemoryEntry,
    UsageStats,
    memory_refiner,
)
from .context_retriever import (
    ContextAwareRetriever,
    TaskContext,
    SkillTrigger,
    RetrievalResult,
    context_aware_retriever,
)
from .internalization import (
    KnowledgeInternalizer,
    InternalizedRule,
    knowledge_internalizer,
)
from .distillation import (
    MultiFacetedDistiller,
    SuccessPattern,
    FailureTrigger,
    ContrastInsight,
    DecisionPoint,
    multi_faceted_distiller,
)
from .meta_evolution import (
    MetaEvolutionLayer,
    StrategyConfig,
    EvolutionResult,
    meta_evolution,
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
    # Curator
    "Curator",
    "CuratorConfig",
    "CuratorState",
    "SkillState",
    "curator",
    # Hindsight Experience Replay
    "HindsightReplay",
    "Trajectory",
    "AntiPattern",
    "FailureType",
    "hindsight_replay",
    # Experience Compression
    "ExperienceCompressor",
    "RawTrajectory",
    "EpisodicMemory",
    "ProceduralSkill",
    "DeclarativeRule",
    "CompressionLevel",
    "experience_compressor",
    # Utility Refiner
    "MemoryRefiner",
    "UtilityScorer",
    "UsageStats",
    "memory_refiner",
    # Context Retriever
    "ContextAwareRetriever",
    "TaskContext",
    "SkillTrigger",
    "RetrievalResult",
    "context_aware_retriever",
    # Knowledge Internalization
    "KnowledgeInternalizer",
    "InternalizedRule",
    "knowledge_internalizer",
    # Multi-faceted Distillation
    "MultiFacetedDistiller",
    "SuccessPattern",
    "FailureTrigger",
    "ContrastInsight",
    "DecisionPoint",
    "multi_faceted_distiller",
    # Meta Evolution
    "MetaEvolutionLayer",
    "StrategyConfig",
    "EvolutionResult",
    "meta_evolution",
]
