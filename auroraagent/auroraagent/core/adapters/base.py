
"""
Model Adapter Base Class
References OpenClaw's provider interface
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Tool call from model"""
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result from tool execution"""
    tool_call_id: str
    content: str
    is_error: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """Unified message structure"""
    role: str
    content: Any
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedResponse:
    """Normalized model response"""
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    reasoning: Optional[str] = None
    raw_response: Any = None
    usage: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelAdapter(ABC):
    """Abstract base class for model adapters"""

    def __init__(self, config):
        self.config = config
        self._initialized = False

    @abstractmethod
    async def initialize(self):
        """Initialize the adapter"""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> NormalizedResponse:
        """Chat with the model"""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[NormalizedResponse, None]:
        """Stream chat with the model"""
        pass

    @abstractmethod
    def chat_sync(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> NormalizedResponse:
        """Synchronous chat with the model"""
        pass
