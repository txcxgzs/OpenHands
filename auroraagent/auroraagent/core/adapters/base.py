"""
模型适配器基类
参考: Hermes Agent ProviderTransport
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class NormalizedResponse:
    """标准化的响应"""
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    reasoning: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


class ModelAdapter(ABC):
    """模型适配器抽象基类"""
    
    @property
    @abstractmethod
    def provider(self) -> str:
        """提供商标识"""
        pass
    
    @abstractmethod
    async def initialize(self, config: Any):
        """初始化适配器"""
        pass
    
    @abstractmethod
    async def call(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> NormalizedResponse:
        """调用模型"""
        pass
    
    @abstractmethod
    def convert_messages(self, messages: List[Dict[str, Any]]) -> Any:
        """转换消息格式"""
        pass
    
    @abstractmethod
    def convert_tools(self, tools: List[Dict]) -> Any:
        """转换工具格式"""
        pass
