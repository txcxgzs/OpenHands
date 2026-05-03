"""
配置管理器 - 简化 API 配置
"""

from typing import Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModelProvider:
    """模型提供商配置"""
    name: str
    env_key: str
    default_model: str
    description: str
    base_url: Optional[str] = None


MODEL_PROVIDERS = {
    "anthropic": ModelProvider(
        name="Anthropic",
        env_key="ANTHROPIC_API_KEY",
        default_model="claude-3-opus-20240229",
        description="Claude 3 Opus/Sonnet - 最强推理能力",
    ),
    "openai": ModelProvider(
        name="OpenAI",
        env_key="OPENAI_API_KEY",
        default_model="gpt-4-turbo-preview",
        description="GPT-4 Turbo - 综合能力强",
    ),
    "longcat": ModelProvider(
        name="LongCat",
        env_key="LONGCAT_API_KEY",
        default_model="LongCat-2.0-Preview",
        description="长上下文模型 - 支持超长对话",
        base_url="https://api.longcat.chat/openai/v1",
    ),
    "deepseek": ModelProvider(
        name="DeepSeek",
        env_key="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        description="国产模型 - 性价比高",
        base_url="https://api.deepseek.com/v1",
    ),
    "openrouter": ModelProvider(
        name="OpenRouter",
        env_key="OPENROUTER_API_KEY",
        default_model="anthropic/claude-3-opus",
        description="聚合 200+ 模型 - 灵活选择",
        base_url="https://openrouter.ai/api/v1",
    ),
    "ollama": ModelProvider(
        name="Ollama",
        env_key="",
        default_model="llama2",
        description="本地模型 - 无需 API Key",
        base_url="http://localhost:11434",
    ),
}


class ConfigManager:
    """
    配置管理器 - 简化 API 配置
    
    特性:
    - 自动检测环境变量
    - 支持 .env 文件
    - 交互式配置向导
    - 一键切换模型
    """
    
    DEFAULT_CONFIG_DIR = Path.home() / ".openhands"
    DEFAULT_ENV_FILE = DEFAULT_CONFIG_DIR / ".env"
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.env_file = self.config_dir / ".env"
        
        self._config: Dict[str, str] = {}
        self._load_env()
    
    def _load_env(self):
        """加载环境变量"""
        # 先加载 .env 文件
        if self.env_file.exists():
            self._load_env_file(self.env_file)
        
        # 环境变量覆盖
        for key, value in os.environ.items():
            if key.upper().endswith("_API_KEY") or key.upper() in [
                "DEFAULT_MODEL", "MAX_ITERATIONS", "GUI_PORT",
                "ENABLE_SELF_EVOLUTION", "ENABLE_WINDOWS_CONTROL",
            ]:
                self._config[key] = value
    
    def _load_env_file(self, file_path: Path):
        """加载 .env 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # 移除引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        if value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        self._config[key] = value
        except Exception as e:
            logger.warning(f"Failed to load env file: {e}")
    
    def get(self, key: str, default: str = "") -> str:
        """获取配置"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: str):
        """设置配置"""
        self._config[key] = value
        os.environ[key] = value
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """获取 API Key"""
        provider_info = MODEL_PROVIDERS.get(provider.lower())
        if provider_info:
            return self._config.get(provider_info.env_key) or os.environ.get(provider_info.env_key)
        return None
    
    def set_api_key(self, provider: str, api_key: str):
        """设置 API Key"""
        provider_info = MODEL_PROVIDERS.get(provider.lower())
        if provider_info:
            self.set(provider_info.env_key, api_key)
    
    def get_default_model(self) -> str:
        """获取默认模型"""
        return self.get("DEFAULT_MODEL", "openai/gpt-4")
    
    def set_default_model(self, model: str):
        """设置默认模型"""
        self.set("DEFAULT_MODEL", model)
    
    def list_configured_providers(self) -> list:
        """列出已配置的提供商"""
        configured = []
        for provider_id, provider in MODEL_PROVIDERS.items():
            if provider.env_key:
                if self.get(provider.env_key) or os.environ.get(provider.env_key):
                    configured.append(provider_id)
            else:
                # Ollama 不需要 API Key
                configured.append(provider_id)
        return configured
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有提供商状态"""
        status = {}
        for provider_id, provider in MODEL_PROVIDERS.items():
            has_key = False
            if provider.env_key:
                has_key = bool(self.get(provider.env_key) or os.environ.get(provider.env_key))
            else:
                has_key = True  # Ollama
            
            status[provider_id] = {
                "name": provider.name,
                "description": provider.description,
                "default_model": provider.default_model,
                "configured": has_key,
                "env_key": provider.env_key,
            }
        return status
    
    def save(self):
        """保存配置到 .env 文件"""
        lines = [
            "# OpenHands 配置文件",
            "# 自动生成 - 可手动编辑",
            "",
        ]
        
        # API Keys
        lines.append("# ========== API Keys ==========")
        for provider_id, provider in MODEL_PROVIDERS.items():
            if provider.env_key:
                value = self._config.get(provider.env_key, "")
                if value:
                    lines.append(f"{provider.env_key}={value}")
                else:
                    lines.append(f"# {provider.env_key}=your_{provider_id}_key_here")
        lines.append("")
        
        # 其他配置
        lines.append("# ========== 其他配置 ==========")
        for key, value in self._config.items():
            if not key.endswith("_API_KEY"):
                lines.append(f"{key}={value}")
        
        with open(self.env_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Config saved to {self.env_file}")
    
    def interactive_setup(self):
        """交互式配置向导"""
        print("\n" + "=" * 60)
        print("OpenHands 配置向导")
        print("=" * 60)
        
        print("\n可用的模型提供商:")
        for i, (provider_id, provider) in enumerate(MODEL_PROVIDERS.items(), 1):
            status = "✓ 已配置" if self.get(provider.env_key) or not provider.env_key else "✗ 未配置"
            print(f"  {i}. {provider.name}: {provider.description} [{status}]")
        
        print("\n选择要配置的提供商 (输入序号，多个用逗号分隔，回车跳过):")
        choice = input("> ").strip()
        
        if choice:
            indices = [int(x.strip()) - 1 for x in choice.split(',') if x.strip().isdigit()]
            providers = list(MODEL_PROVIDERS.keys())
            
            for idx in indices:
                if 0 <= idx < len(providers):
                    provider_id = providers[idx]
                    provider = MODEL_PROVIDERS[provider_id]
                    
                    if provider.env_key:
                        print(f"\n配置 {provider.name}:")
                        print(f"  获取 API Key: ", end="")
                        if provider_id == "anthropic":
                            print("https://console.anthropic.com/")
                        elif provider_id == "openai":
                            print("https://platform.openai.com/api-keys")
                        elif provider_id == "longcat":
                            print("https://longcat.chat/")
                        elif provider_id == "deepseek":
                            print("https://platform.deepseek.com/")
                        elif provider_id == "openrouter":
                            print("https://openrouter.ai/keys")
                        
                        api_key = input(f"  输入 API Key: ").strip()
                        if api_key:
                            self.set_api_key(provider_id, api_key)
                            print(f"  ✓ {provider.name} 配置成功")
        
        # 选择默认模型
        print("\n选择默认模型:")
        configured = self.list_configured_providers()
        for i, provider_id in enumerate(configured, 1):
            provider = MODEL_PROVIDERS[provider_id]
            print(f"  {i}. {provider.name}: {provider.default_model}")
        
        if configured:
            model_choice = input("输入序号 (回车使用第一个): ").strip()
            if model_choice.isdigit():
                idx = int(model_choice) - 1
                if 0 <= idx < len(configured):
                    provider_id = configured[idx]
                    provider = MODEL_PROVIDERS[provider_id]
                    self.set_default_model(f"{provider_id}/{provider.default_model}")
            elif configured:
                provider_id = configured[0]
                provider = MODEL_PROVIDERS[provider_id]
                self.set_default_model(f"{provider_id}/{provider.default_model}")
        
        # 保存配置
        self.save()
        
        print("\n" + "=" * 60)
        print("✓ 配置完成!")
        print("=" * 60)


config_manager = ConfigManager()


def quick_setup():
    """快速配置入口"""
    config_manager.interactive_setup()


if __name__ == "__main__":
    quick_setup()
