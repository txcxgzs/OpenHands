"""
Microsoft Teams 通道集成
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import asyncio
import logging
from .base import BaseChannel, ChannelMessage

logger = logging.getLogger(__name__)


@dataclass
class TeamsConfig:
    app_id: str
    app_secret: str
    tenant_id: str
    bot_id: Optional[str] = None


class TeamsChannel(BaseChannel):
    """Microsoft Teams 通道 - Bot Framework"""

    def __init__(self, config: Dict[str, Any]):
        self._config = TeamsConfig(
            app_id=config.get("app_id", ""),
            app_secret=config.get("app_secret", ""),
            tenant_id=config.get("tenant_id", ""),
            bot_id=config.get("bot_id"),
        )
        self._access_token: Optional[str] = None
        self._service_url = "https://smba.trafficmanager.net/teams/"
        self._message_handler: Optional[callable] = None

    async def connect(self) -> None:
        """获取访问令牌"""
        import httpx

        url = f"https://login.microsoftonline.com/{self._config.tenant_id}/oauth2/v2.0/token"

        data = {
            "grant_type": "client_credentials",
            "client_id": self._config.app_id,
            "client_secret": self._config.app_secret,
            "scope": "https://api.botframework.com/.default",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            token_data = response.json()
            self._access_token = token_data["access_token"]

        logger.info("Teams 连接成功")

    async def send_message(self, msg: ChannelMessage) -> None:
        """发送消息"""
        if not self._access_token:
            await self.connect()

        import httpx

        url = f"{self._service_url}v3/conversations/{msg.channel}/activities"

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "type": "message",
            "text": msg.content,
            "from": {
                "id": self._config.bot_id or self._config.app_id,
                "name": "OpenHands Bot",
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Teams 消息已发送: {msg.channel}")

    async def send_card(
        self,
        channel: str,
        card: Dict[str, Any],
    ) -> None:
        """发送自适应卡片"""
        if not self._access_token:
            await self.connect()

        import httpx

        url = f"{self._service_url}v3/conversations/{channel}/activities"

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

    async def receive_messages(self) -> List[ChannelMessage]:
        """接收消息"""
        return []

    def set_message_handler(self, handler: callable) -> None:
        """设置消息处理器"""
        self._message_handler = handler

    async def handle_activity(self, activity: Dict[str, Any]) -> None:
        """处理活动事件"""
        if activity.get("type") != "message":
            return

        msg = ChannelMessage(
            content=activity.get("text", ""),
            channel=activity.get("conversation", {}).get("id", ""),
            user_id=activity.get("from", {}).get("id", ""),
            user_name=activity.get("from", {}).get("name", ""),
        )

        if self._message_handler:
            await self._message_handler(msg)
