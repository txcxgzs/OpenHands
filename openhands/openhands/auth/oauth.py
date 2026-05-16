"""
OAuth 认证系统 - OpenClaw 风格
"""

from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class OAuthProvider(str, Enum):
    GOOGLE = "google"
    GITHUB = "github"
    SLACK = "slack"
    DISCORD = "discord"
    MICROSOFT = "microsoft"


@dataclass
class OAuthConfig:
    provider: OAuthProvider
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]
    auth_url: str
    token_url: str
    userinfo_url: str


@dataclass
class OAuthToken:
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_at: datetime
    scopes: list[str]

    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at - timedelta(minutes=5)


@dataclass
class OAuthUser:
    provider: str
    user_id: str
    email: Optional[str]
    name: Optional[str]
    avatar_url: Optional[str]
    raw_data: Dict[str, Any]


class OAuthManager:
    """
    OAuth 2.0 认证管理器
    参考 OpenClaw 的 OAuth 系统
    """

    def __init__(self):
        self._configs: Dict[OAuthProvider, OAuthConfig] = {}
        self._tokens: Dict[str, OAuthToken] = {}
        self._users: Dict[str, OAuthUser] = {}

    def register_provider(self, config: OAuthConfig) -> None:
        """注册 OAuth 提供商"""
        self._configs[config.provider] = config
        logger.info(f"OAuth provider registered: {config.provider}")

    def get_authorization_url(self, provider: OAuthProvider) -> str:
        """获取授权 URL"""
        import urllib.parse

        config = self._configs.get(provider)
        if not config:
            raise ValueError(f"Provider {provider} not registered")

        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
        }

        return f"{config.auth_url}?{urllib.parse.urlencode(params)}"

    async def exchange_code(
        self,
        provider: OAuthProvider,
        code: str,
    ) -> OAuthToken:
        """交换授权码获取 Token"""
        import httpx

        config = self._configs.get(provider)
        if not config:
            raise ValueError(f"Provider {provider} not registered")

        data = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config.redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(config.token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

        expires_in = token_data.get("expires_in", 3600)
        token = OAuthToken(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=datetime.now() + timedelta(seconds=expires_in),
            scopes=token_data.get("scope", "").split(),
        )

        return token

    async def get_user_info(
        self,
        provider: OAuthProvider,
        token: OAuthToken,
    ) -> OAuthUser:
        """获取用户信息"""
        import httpx

        config = self._configs.get(provider)
        if not config:
            raise ValueError(f"Provider {provider} not registered")

        headers = {
            "Authorization": f"{token.token_type} {token.access_token}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(config.userinfo_url, headers=headers)
            response.raise_for_status()
            data = response.json()

        user = OAuthUser(
            provider=provider.value,
            user_id=data.get("id", data.get("sub", "")),
            email=data.get("email"),
            name=data.get("name"),
            avatar_url=data.get("picture", data.get("avatar_url")),
            raw_data=data,
        )

        return user

    def store_token(self, session_id: str, token: OAuthToken) -> None:
        """存储 Token"""
        self._tokens[session_id] = token
        logger.info(f"Token stored for session: {session_id}")

    def get_token(self, session_id: str) -> Optional[OAuthToken]:
        """获取 Token"""
        return self._tokens.get(session_id)

    def store_user(self, session_id: str, user: OAuthUser) -> None:
        """存储用户信息"""
        self._users[session_id] = user

    def get_user(self, session_id: str) -> Optional[OAuthUser]:
        """获取用户信息"""
        return self._users.get(session_id)

    async def refresh_token(
        self,
        provider: OAuthProvider,
        refresh_token: str,
    ) -> OAuthToken:
        """刷新 Token"""
        import httpx

        config = self._configs.get(provider)
        if not config:
            raise ValueError(f"Provider {provider} not registered")

        data = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(config.token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

        expires_in = token_data.get("expires_in", 3600)
        token = OAuthToken(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", refresh_token),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=datetime.now() + timedelta(seconds=expires_in),
            scopes=token_data.get("scope", "").split(),
        )

        return token

    def list_providers(self) -> list[OAuthProvider]:
        """列出已注册的提供商"""
        return list(self._configs.keys())


# 常用提供商配置模板
PROVIDER_CONFIGS = {
    OAuthProvider.GOOGLE: {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": ["openid", "email", "profile"],
    },
    OAuthProvider.GITHUB: {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scopes": ["user:email", "read:user"],
    },
    OAuthProvider.SLACK: {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "userinfo_url": "https://slack.com/api/auth.test",
        "scopes": ["channels:read", "chat:write", "users:read"],
    },
}
