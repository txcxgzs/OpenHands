"""
WhatsApp 通道集成
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import asyncio
import logging
from .base import BaseChannel, ChannelMessage

logger = logging.getLogger(__name__)


@dataclass
class WhatsAppConfig:
    phone_number_id: str
    access_token: str
    business_account_id: Optional[str] = None
    api_version: str = "v18.0"
    webhook_verify_token: Optional[str] = None


class WhatsAppChannel(BaseChannel):
    """WhatsApp Business API 通道"""

    def __init__(self, config: Dict[str, Any]):
        self._config = WhatsAppConfig(
            phone_number_id=config.get("phone_number_id", ""),
            access_token=config.get("access_token", ""),
            business_account_id=config.get("business_account_id"),
            api_version=config.get("api_version", "v18.0"),
            webhook_verify_token=config.get("webhook_verify_token"),
        )
        self._base_url = f"https://graph.facebook.com/{self._config.api_version}"
        self._webhook_secret = config.get("webhook_secret", "")
        self._message_handler: Optional[callable] = None

    async def connect(self) -> None:
        """连接 WhatsApp API"""
        import httpx

        url = f"{self._base_url}/{self._config.phone_number_id}"
        headers = {
            "Authorization": f"Bearer {self._config.access_token}",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                logger.info("WhatsApp 连接成功")
            except Exception as e:
                logger.error(f"WhatsApp 连接失败: {e}")
                raise

    async def send_message(self, msg: ChannelMessage) -> None:
        """发送 WhatsApp 消息"""
        import httpx

        url = f"{self._base_url}/{self._config.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._config.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": msg.user_id,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": msg.content,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"WhatsApp 消息已发送: {msg.user_id}")

    async def send_image(
        self,
        recipient: str,
        image_url: str,
        caption: Optional[str] = None,
    ) -> None:
        """发送图片消息"""
        import httpx

        url = f"{self._base_url}/{self._config.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._config.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "image",
            "image": {
                "link": image_url,
                "caption": caption or "",
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

    async def receive_messages(self) -> List[ChannelMessage]:
        """接收消息（需要 webhook）"""
        return []

    def set_message_handler(self, handler: callable) -> None:
        """设置消息处理器"""
        self._message_handler = handler

    async def handle_webhook(self, payload: Dict[str, Any]) -> None:
        """处理 webhook 事件"""
        if "entry" not in payload:
            return

        for entry in payload["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for message in value["messages"]:
                        msg = ChannelMessage(
                            content=message.get("text", {}).get("body", ""),
                            channel="whatsapp",
                            user_id=message["from"],
                            user_name=message.get("from", ""),
                            ts=message.get("timestamp"),
                        )

                        if self._message_handler:
                            await self._message_handler(msg)

    def verify_webhook(self, mode: str, token: str) -> bool:
        """验证 webhook"""
        if mode == "subscribe" and token == self._config.webhook_verify_token:
            return True
        return False
