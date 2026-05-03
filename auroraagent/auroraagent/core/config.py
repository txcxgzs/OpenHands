"""
AuroraAgent 配置系统
参考: OpenClaw Config System, Hermes Agent Config
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from dotenv import load_dotenv


@dataclass
class ModelConfig:
    """模型配置"""
    provider: str = "anthropic"
    model: str = "claude-3-5-sonnet-20241022"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9


@dataclass
class WindowsControlConfig:
    """Windows 控制配置"""
    enabled: bool = True
    mouse_speed: float = 1.0
    keyboard_delay: float = 0.1
    safe_mode: bool = True  # 安全模式 - 限制危险操作
    screen_capture_enabled: bool = True


@dataclass
class MemoryConfig:
    """记忆系统配置"""
    enabled: bool = True
    max_history: int = 50
    auto_compress: bool = True
    compress_threshold: float = 0.8


@dataclass
class AgentConfig:
    """Agent 主配置"""
    name: str = "Aurora"
    home_dir: Path = field(default_factory=lambda: Path.home() / ".auroraagent")
    
    model: ModelConfig = field(default_factory=ModelConfig)
    windows: WindowsControlConfig = field(default_factory=WindowsControlConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    
    enabled_toolsets: List[str] = field(
        default_factory=lambda: ["file", "terminal", "windows", "multimodal"]
    )
    disabled_toolsets: List[str] = field(default_factory=list)
    
    max_iterations: int = 50
    auto_save: bool = True
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "AgentConfig":
        """从文件加载配置"""
        load_dotenv()
        
        config_path = config_path or cls._get_default_config_path()
        
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return cls.from_dict(data)
        
        return cls()
    
    @classmethod
    def _get_default_config_path(cls) -> Path:
        """获取默认配置路径"""
        config_home = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        return Path(config_home) / "auroraagent" / "config.yaml"
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AgentConfig":
        """从字典创建配置"""
        config = cls()
        
        if "name" in data:
            config.name = data["name"]
        
        if "model" in data:
            config.model = ModelConfig(**data["model"])
        
        if "windows" in data:
            config.windows = WindowsControlConfig(**data["windows"])
        
        if "memory" in data:
            config.memory = MemoryConfig(**data["memory"])
        
        if "enabled_toolsets" in data:
            config.enabled_toolsets = data["enabled_toolsets"]
        
        if "disabled_toolsets" in data:
            config.disabled_toolsets = data["disabled_toolsets"]
        
        if "max_iterations" in data:
            config.max_iterations = data["max_iterations"]
        
        # 从环境变量加载 API Key
        if not config.model.api_key:
            config.model.api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        
        return config
    
    def save(self, config_path: Optional[Path] = None):
        """保存配置到文件"""
        config_path = config_path or self._get_default_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "name": self.name,
            "model": {
                "provider": self.model.provider,
                "model": self.model.model,
                "base_url": self.model.base_url,
                "max_tokens": self.model.max_tokens,
                "temperature": self.model.temperature,
                "top_p": self.model.top_p,
            },
            "windows": {
                "enabled": self.windows.enabled,
                "mouse_speed": self.windows.mouse_speed,
                "keyboard_delay": self.windows.keyboard_delay,
                "safe_mode": self.windows.safe_mode,
                "screen_capture_enabled": self.windows.screen_capture_enabled,
            },
            "memory": {
                "enabled": self.memory.enabled,
                "max_history": self.memory.max_history,
                "auto_compress": self.memory.auto_compress,
                "compress_threshold": self.memory.compress_threshold,
            },
            "enabled_toolsets": self.enabled_toolsets,
            "disabled_toolsets": self.disabled_toolsets,
            "max_iterations": self.max_iterations,
            "auto_save": self.auto_save,
        }
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def get_data_dir(self) -> Path:
        """获取数据目录"""
        data_dir = self.home_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    
    def get_sessions_dir(self) -> Path:
        """获取会话目录"""
        sessions_dir = self.home_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return sessions_dir
