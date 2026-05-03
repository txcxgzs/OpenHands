"""
Webhook 支持系统 - OpenClaw 风格
"""

from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import hashlib
import hmac
import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class WebhookEvent(str, Enum):
    MESSAGE = "message"
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class WebhookConfig:
    url: str
    events: List[WebhookEvent]
    secret: Optional[str] = None
    enabled: bool = True
    retry_count: int = 3
    timeout: int = 30
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class WebhookPayload:
    event: str
    timestamp: str
    data: Dict[str, Any]
    signature: Optional[str] = None


class WebhookManager:
    """
    Webhook 管理器 - 支持事件订阅和分发
    参考 OpenClaw 的 webhook 系统
    """

    def __init__(self):
        self._webhooks: Dict[str, WebhookConfig] = {}
        self._handlers: Dict[WebhookEvent, List[Callable]] = {}
        self._delivery_history: List[Dict[str, Any]] = []

    def register_webhook(
        self,
        webhook_id: str,
        config: WebhookConfig,
    ) -> None:
        """注册 webhook"""
        self._webhooks[webhook_id] = config
        logger.info(f"Webhook registered: {webhook_id} -> {config.url}")

    def unregister_webhook(self, webhook_id: str) -> bool:
        """取消注册 webhook"""
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            logger.info(f"Webhook unregistered: {webhook_id}")
            return True
        return False

    def add_handler(
        self,
        event: WebhookEvent,
        handler: Callable,
    ) -> None:
        """添加事件处理器"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def _generate_signature(
        self,
        payload: str,
        secret: str,
    ) -> str:
        """生成 HMAC 签名"""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    async def trigger(
        self,
        event: WebhookEvent,
        data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """触发 webhook"""
        if event not in self._handlers:
            return []

        results = []

        for webhook_id, config in self._webhooks.items():
            if not config.enabled:
                continue

            if event not in config.events:
                continue

            payload = WebhookPayload(
                event=event.value,
                timestamp=datetime.now().isoformat(),
                data=data,
            )

            payload_json = json.dumps(payload.__dict__, default=str)
            if config.secret:
                payload.signature = self._generate_signature(
                    payload_json,
                    config.secret
                )

            success = await self._deliver_webhook(config, payload_json)
            results.append({
                "webhook_id": webhook_id,
                "success": success,
                "event": event.value,
            })

        for handler in self._handlers.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Handler error for {event}: {e}")

        return results

    async def _deliver_webhook(
        self,
        config: WebhookConfig,
        payload: str,
    ) -> bool:
        """投递 webhook"""
        import httpx

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OpenHands-Webhook/1.0",
            **config.headers,
        }

        for attempt in range(config.retry_count):
            try:
                async with httpx.AsyncClient(timeout=config.timeout) as client:
                    response = await client.post(
                        config.url,
                        content=payload,
                        headers=headers,
                    )

                    if response.status_code < 400:
                        logger.info(f"Webhook delivered: {config.url}")
                        return True

                    logger.warning(
                        f"Webhook failed (attempt {attempt+1}): "
                        f"{response.status_code}"
                    )

            except Exception as e:
                logger.error(f"Webhook delivery error: {e}")

            await asyncio.sleep(1 * (attempt + 1))

        return False

    def get_webhooks(self) -> Dict[str, WebhookConfig]:
        return self._webhooks.copy()

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._delivery_history[-limit:]


class WebhookTool:
    """Webhook 工具"""

    def __init__(self, manager: WebhookManager):
        self._manager = manager

    def register_tools(self, registry):
        @registry.register_tool(
            name="webhook_register",
            description="注册 webhook",
            toolset="webhook",
            parameters={
                "webhook_id": {"type": "string"},
                "url": {"type": "string"},
                "events": {"type": "array"},
                "secret": {"type": "string"},
            },
        )
        async def register_webhook(
            webhook_id: str,
            url: str,
            events: List[str],
            secret: Optional[str] = None,
        ) -> str:
            try:
                config = WebhookConfig(
                    url=url,
                    events=[WebhookEvent(e) for e in events],
                    secret=secret,
                )
                self._manager.register_webhook(webhook_id, config)
                return f"✓ Webhook {webhook_id} registered"
            except Exception as e:
                return f"✗ Error: {e}"

        @registry.register_tool(
            name="webhook_unregister",
            description="取消注册 webhook",
            toolset="webhook",
            parameters={
                "webhook_id": {"type": "string"},
            },
        )
        async def unregister_webhook(webhook_id: str) -> str:
            if self._manager.unregister_webhook(webhook_id):
                return f"✓ Webhook {webhook_id} unregistered"
            return f"✗ Webhook {webhook_id} not found"

        @registry.register_tool(
            name="webhook_list",
            description="列出所有 webhook",
            toolset="webhook",
            parameters={},
        )
        async def list_webhooks() -> str:
            webhooks = self._manager.get_webhooks()
            if not webhooks:
                return "No webhooks registered"

            lines = ["Registered Webhooks:"]
            for wid, cfg in webhooks.items():
                lines.append(f"- {wid}: {cfg.url} ({len(cfg.events)} events)")
            return "\n".join(lines)

        logger.debug("Webhook tools registered")
