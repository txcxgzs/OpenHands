

"""
Agent Configuration System
References OpenClaw's model and tool configuration
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Model provider configuration"""
    provider: str = "anthropic"
    model: str = "claude-3-5-sonnet-20241022"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    max_retries: int = 3
    timeout: int = 60
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryConfig:
    """Memory system configuration"""
    enabled: bool = True
    path: str = "./data/memory"
    max_items: int = 10000
    vector_embedding_provider: str = "local"
    embedding_dim: int = 1536
    similarity_threshold: float = 0.7


@dataclass
class ToolConfig:
    """Tool policy configuration"""
    default_profile: str = "coding"
    sandbox_enabled: bool = False
    workspace_root: Optional[str] = None
    allowed_paths: Optional[List[str]] = None
    denied_paths: Optional[List[str]] = None
    require_approval: Optional[List[str]] = None


@dataclass
class WindowsConfig:
    """Windows automation configuration"""
    enabled: bool = True
    screenshot_path: str = "./data/screenshots"
    keyboard_delay: float = 0.05
    mouse_delay: float = 0.1


@dataclass
class AgentConfig:
    """Main agent configuration - OpenClaw style unified config"""
    model: ModelConfig = field(default_factory=ModelConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    windows: WindowsConfig = field(default_factory=WindowsConfig)

    max_iterations: int = 50
    agent_id: str = "aurora-agent"
    system_prompt: Optional[str] = None

    @classmethod
    def load(cls, config_path: Optional[str] = None):
        """Load config from file or environment"""
        config = cls()

        if config_path and Path(config_path).exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    config._apply_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")

        config._apply_env_vars()
        return config

    def _apply_dict(self, data):
        """Apply config from dictionary"""
        if "model" in data:
            self._update_dataclass(self.model, data["model"])
        if "memory" in data:
            self._update_dataclass(self.memory, data["memory"])
        if "tools" in data:
            self._update_dataclass(self.tools, data["tools"])
        if "windows" in data:
            self._update_dataclass(self.windows, data["windows"])
        if "max_iterations" in data:
            self.max_iterations = data["max_iterations"]
        if "agent_id" in data:
            self.agent_id = data["agent_id"]
        if "system_prompt" in data:
            self.system_prompt = data["system_prompt"]

    def _apply_env_vars(self):
        """Apply config from environment variables"""
        # Load provider and model from environment
        env_provider = os.getenv("DEFAULT_PROVIDER")
        if env_provider:
            self.model.provider = env_provider
            
        env_model = os.getenv("DEFAULT_MODEL")
        if env_model:
            self.model.model = env_model
            
        # Load API Key
        if not self.model.api_key:
            if self.model.provider == "anthropic":
                self.model.api_key = os.getenv("ANTHROPIC_API_KEY")
            elif self.model.provider == "openai":
                self.model.api_key = os.getenv("OPENAI_API_KEY")
            elif self.model.provider == "longcat":
                self.model.api_key = os.getenv("LONGCAT_API_KEY")
            elif self.model.provider == "deepseek":
                self.model.api_key = os.getenv("DEEPSEEK_API_KEY")

        if not self.model.base_url:
            if self.model.provider == "anthropic":
                self.model.base_url = os.getenv("ANTHROPIC_BASE_URL")
            elif self.model.provider == "openai":
                self.model.base_url = os.getenv("OPENAI_BASE_URL")
            elif self.model.provider == "longcat":
                self.model.base_url = os.getenv("LONGCAT_BASE_URL")
            elif self.model.provider == "deepseek":
                self.model.base_url = os.getenv("DEEPSEEK_BASE_URL")

    @staticmethod
    def _update_dataclass(obj, data):
        """Update dataclass fields from dict"""
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

    def save(self, config_path):
        """Save config to file"""
        data = {
            "model": {
                "provider": self.model.provider,
                "model": self.model.model,
                "base_url": self.model.base_url,
                "temperature": self.model.temperature,
                "max_tokens": self.model.max_tokens,
                "max_retries": self.model.max_retries,
                "timeout": self.model.timeout,
            },
            "memory": {
                "enabled": self.memory.enabled,
                "path": self.memory.path,
                "max_items": self.memory.max_items,
                "vector_embedding_provider": self.memory.vector_embedding_provider,
                "embedding_dim": self.memory.embedding_dim,
                "similarity_threshold": self.memory.similarity_threshold,
            },
            "tools": {
                "default_profile": self.tools.default_profile,
                "sandbox_enabled": self.tools.sandbox_enabled,
                "workspace_root": self.tools.workspace_root,
                "allowed_paths": self.tools.allowed_paths,
                "denied_paths": self.tools.denied_paths,
                "require_approval": self.tools.require_approval,
            },
            "windows": {
                "enabled": self.windows.enabled,
                "screenshot_path": self.windows.screenshot_path,
                "keyboard_delay": self.windows.keyboard_delay,
                "mouse_delay": self.windows.mouse_delay,
            },
            "max_iterations": self.max_iterations,
            "agent_id": self.agent_id,
            "system_prompt": self.system_prompt,
        }

        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
