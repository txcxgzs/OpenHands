"""
Plugins Package - References OpenClaw's plugin SDK
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import logging
import importlib
import sys

logger = logging.getLogger(__name__)


@dataclass
class PluginMetadata:
    """Plugin metadata"""
    name: str
    version: str
    description: str
    author: str = ""
    dependencies: List[str] = field(default_factory=list)


class Plugin:
    """Base plugin class"""

    metadata: PluginMetadata

    def on_load(self):
        """Called when plugin is loaded"""
        pass

    def on_unload(self):
        """Called when plugin is unloaded"""
        pass

    def register_tools(self, registry):
        """Register plugin tools"""
        pass

    def register_hooks(self, hooks):
        """Register lifecycle hooks"""
        pass


class PluginManager:
    """
    Manages plugins
    References OpenClaw's plugin SDK
    """

    def __init__(self, agent):
        self.agent = agent
        self._plugins: Dict[str, Plugin] = {}
        self._hooks: Dict[str, List[Callable]] = {}

    def load_plugin(self, name: str, plugin_class: type) -> bool:
        """Load a plugin"""
        try:
            plugin = plugin_class()
            plugin.on_load()
            plugin.register_tools(self.agent._tool_registry)
            plugin.register_hooks(self)
            self._plugins[name] = plugin
            logger.info(f"Loaded plugin: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")
            return False

    def load_plugin_from_module(self, name: str, module_path: str) -> bool:
        """Load plugin from module path"""
        try:
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, "plugin", None)
            if not plugin_class:
                logger.error(f"No 'plugin' class in {module_path}")
                return False
            return self.load_plugin(name, plugin_class)
        except Exception as e:
            logger.error(f"Failed to load plugin from {module_path}: {e}")
            return False

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin"""
        plugin = self._plugins.get(name)
        if plugin:
            try:
                plugin.on_unload()
                del self._plugins[name]
                logger.info(f"Unloaded plugin: {name}")
                return True
            except Exception as e:
                logger.error(f"Failed to unload plugin {name}: {e}")
        return False

    def get_plugin(self, name: str) -> Optional[Plugin]:
        return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        return list(self._plugins.keys())

    def register_hook(self, name: str, callback: Callable):
        if name not in self._hooks:
            self._hooks[name] = []
        self._hooks[name].append(callback)

    async def trigger_hook(self, name: str, *args, **kwargs):
        callbacks = self._hooks.get(name, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook {name} failed: {e}")


import asyncio
