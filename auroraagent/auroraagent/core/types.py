
"""
Core Type Definitions for AuroraAgent
References OpenClaw's type system
"""

from typing import (
    Dict, List, Any, Optional, Union, AsyncGenerator, Callable, TypeVar, Generic
)
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

T = TypeVar("T")


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class MessageContentBlock:
    """Multimodal content block (text, image, etc.)"""
    type: str = "text"
    text: Optional[str] = None
    source: Optional[Dict[str, Any]] = None


@dataclass
class ToolCall:
    """Tool call from model"""
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result from executing a tool"""
    tool_call_id: str
    content: str
    is_error: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """Unified message structure for all providers"""
    role: MessageRole
    content: Union[str, List[MessageContentBlock]]
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NormalizedResponse:
    """Normalized response from any model provider"""
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    raw_response: Any = None
    usage: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRunMeta:
    """Metadata for agent runs (OpenClaw style)"""
    session_id: str
    agent_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    iteration_count: int = 0
    tool_call_count: int = 0
    error_count: int = 0


@dataclass
class AgentRunResult:
    """Result of an agent run"""
    meta: AgentRunMeta
    final_answer: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class ToolAccessLevel(Enum):
    """Tool access permission levels"""
    DISABLED = auto()
    RESTRICTED = auto()
    ALLOWED = auto()
    OWNER_ONLY = auto()


@dataclass
class ToolProfile:
    """Tool profile for policy management"""
    name: str
    description: str = ""
    allowed_tools: Optional[List[str]] = None
    denied_tools: Optional[List[str]] = None
    require_approval: Optional[List[str]] = None


class SessionStatus(Enum):
    """Session lifecycle status"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class SessionState:
    """Session state tracking"""
    session_id: str
    status: SessionStatus = SessionStatus.IDLE
    messages: List[Message] = field(default_factory=list)
    current_tool_profile: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
