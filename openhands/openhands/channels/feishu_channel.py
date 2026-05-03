"""
飞书/钉钉 通道集成
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import asyncio
import logging
from .base import BaseChannel, ChannelMessage

logger = logging.getLogger(__name__)


@dataclass
class FeishuConfig:
    app_id: str
    app_secret: str
    encrypt_key: Optional[str] = None
    verification_token: Optional[str] = None


class FeishuChannel(BaseChannel):
    """飞书/Lark 通道"""

    def __init__(self, config: Dict[str, Any]):
        self._config = FeishuConfig(
            app_id=config.get("app_id", ""),
            app_secret=config.get("app_secret", ""),
            encrypt_key=config.get("encrypt_key"),
            verification_token=config.get("verification_token"),
        )
        self._tenant_access_token: Optional[str] = None
        self._base_url = "https://open.feishu.cn/open-apis"
        self._message_handler: Optional[callable] = None

    async def connect(self) -> None:
        """获取 tenant access token"""
        import httpx

        url = f"{self._base_url}/auth/v3/tenant_access_token/internal"

        payload = {
            "app_id": self._config.app_id,
            "app_secret": self._config.app_secret,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                raise Exception(f"Failed to get token: {data}")

            self._tenant_access_token = data["tenant_access_token"]

        logger.info("飞书连接成功")

    async def _ensure_token(self) -> str:
        """确保 token 有效"""
        if not self._tenant_access_token:
            await self.connect()
        return self._tenant_access_token

    async def send_message(self, msg: ChannelMessage) -> None:
        """发送消息"""
        token = await self._ensure_token()

        import httpx

        url = f"{self._base_url}/im/v1/messages?receive_id_type=open_id"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "receive_id": msg.user_id,
            "msg_type": "text",
            "content": json.dumps({"text": msg.content}),
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                raise Exception(f"Failed to send message: {data}")

        logger.info(f"飞书消息已发送: {msg.user_id}")

    async def send_card(
        self,
        user_id: str,
        card_content: Dict[str, Any],
    ) -> None:
        """发送卡片消息"""
        token = await self._ensure_token()

        import httpx

        url = f"{self._base_url}/im/v1/messages?receive_id_type=open_id"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "receive_id": user_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content),
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

    async def handle_event(self, event: Dict[str, Any]) -> None:
        """处理事件"""
        if event.get("event", {}).get("type") != "im.message.receive_v1":
            return

        message = event.get("event", {}).get("message", {})
        sender = event.get("event", {}).get("sender", {})

        msg = ChannelMessage(
            content=message.get("content", ""),
            channel=message.get("chat_id", ""),
            user_id=sender.get("sender_id", {}).get("open_id", ""),
            user_name=sender.get("sender_name", ""),
            ts=message.get("create_time"),
        )

        if self._message_handler:
            await self._message_handler(msg)

    def verify_event(self, timestamp: str, nonce: str, signature: str) -> bool:
        """验证事件签名"""
        if not self._config.encrypt_key:
            return True

        import hashlib
        import hmac

        string_to_sign = f"{timestamp}{nonce}{self._config.encrypt_key}"
        my_signature = hmac.new(
            self._config.encrypt_key.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()

        return my_signature == signature
