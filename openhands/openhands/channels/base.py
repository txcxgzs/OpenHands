"""
Channels Package - References OpenClaw's channel integrations
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ChannelMessage:
    """Channel message structure"""
    channel_id: str
    user_id: str
    content: str
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelConfig:
    """Channel configuration"""
    name: str
    enabled: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)


class Channel(ABC):
    """Abstract channel base"""

    def __init__(self, config: ChannelConfig):
        self.config = config
        self._running = False

    @abstractmethod
    async def start(self):
        pass

    @abstractmethod
    async def stop(self):
        pass

    @abstractmethod
    async def send(self, user_id: str, content: str):
        pass


class ChannelManager:
    """
    Manages channel integrations
    References OpenClaw's channel system
    """

    def __init__(self, agent):
        self.agent = agent
        self._channels: Dict[str, Channel] = {}
        self._handlers: Dict[str, Callable] = {}

    def register_channel(self, name: str, channel: Channel):
        self._channels[name] = channel
        logger.info(f"Registered channel: {name}")

    def get_channel(self, name: str) -> Optional[Channel]:
        return self._channels.get(name)

    def list_channels(self) -> List[str]:
        return list(self._channels.keys())

    async def start_all(self):
        for channel in self._channels.values():
            await channel.start()

    async def stop_all(self):
        for channel in self._channels.values():
            await channel.stop()

    def on_message(self, channel_name: str, handler: Callable):
        self._handlers[channel_name] = handler

    async def handle_message(self, channel_name: str, message: ChannelMessage):
        handler = self._handlers.get(channel_name)
        if handler:
            await handler(message)


class CLIChannel(Channel):
    """CLI Channel for interactive terminal use"""

    async def start(self):
        self._running = True
        logger.info("CLI channel started")

    async def stop(self):
        self._running = False

    async def send(self, user_id: str, content: str):
        print(f"[CLI] {content}")


class WebhookChannel(Channel):
    """Webhook Channel for HTTP callbacks"""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self._webhook_url: Optional[str] = None

    async def start(self):
        self._webhook_url = self.config.settings.get("webhook_url")
        self._running = True
        logger.info(f"Webhook channel started: {self._webhook_url}")

    async def stop(self):
        self._running = False

    async def send(self, user_id: str, content: str):
        if not self._webhook_url:
            return

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(
                    self._webhook_url,
                    json={"user_id": user_id, "content": content},
                    timeout=10.0,
                )
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
