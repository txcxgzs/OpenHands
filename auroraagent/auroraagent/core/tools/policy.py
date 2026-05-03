
"""
Tool Policy System - Deep reference to OpenClaw's tool-policy.ts
"""

from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
import logging
from ..types import ToolProfile

logger = logging.getLogger(__name__)


@dataclass
class ToolPolicy:
    """Complete tool policy"""
    allowed_tools: Optional[List[str]] = None
    denied_tools: Optional[List[str]] = None
    require_approval: Optional[List[str]] = None
    require_owner: Optional[List[str]] = None

    def is_allowed(self, tool_name: str) -> bool:
        tool_name = tool_name.lower()

        if self.denied_tools and tool_name in [t.lower() for t in self.denied_tools]:
            return False

        if self.allowed_tools:
            return tool_name in [t.lower() for t in self.allowed_tools]

        return True

    def needs_approval(self, tool_name: str) -> bool:
        if not self.require_approval:
            return False
        return tool_name.lower() in [t.lower() for t in self.require_approval]

    def needs_owner(self, tool_name: str) -> bool:
        if not self.require_owner:
            return False
        return tool_name.lower() in [t.lower() for t in self.require_owner]


class ToolPolicyManager:
    """
    Manages tool profiles and policies
    References OpenClaw's tool policy pipeline
    """

    def __init__(self):
        self._profiles: Dict[str, ToolProfile] = {}
        self._policies: Dict[str, ToolPolicy] = {}
        self._default_profile: Optional[str] = None
        self._init_default_profiles()

    def _init_default_profiles(self):
        self._profiles["minimal"] = ToolProfile(
            name="minimal",
            description="Minimal tools only",
            allowed_tools=["read", "memory_search", "session_status"],
            denied_tools=[],
            require_approval=[],
        )

        self._profiles["coding"] = ToolProfile(
            name="coding",
            description="Coding-focused tools",
            allowed_tools=[
                "read", "write", "edit", "exec", "terminal",
                "memory_add", "memory_search", "memory_list",
                "web_search", "web_fetch", "screenshot",
                "list_windows", "activate_window",
            ],
            denied_tools=[],
            require_approval=["exec"],
        )

        self._profiles["full"] = ToolProfile(
            name="full",
            description="All tools enabled",
            allowed_tools=None,
            denied_tools=None,
            require_approval=["exec"],
        )

        self._default_profile = "coding"

        for name, profile in self._profiles.items():
            self._policies[name] = ToolPolicy(
                allowed_tools=profile.allowed_tools,
                denied_tools=profile.denied_tools,
                require_approval=profile.require_approval,
            )

    def add_profile(self, profile: ToolProfile):
        self._profiles[profile.name] = profile
        self._policies[profile.name] = ToolPolicy(
            allowed_tools=profile.allowed_tools,
            denied_tools=profile.denied_tools,
            require_approval=profile.require_approval,
        )

    def get_profile(self, name: str) -> Optional[ToolProfile]:
        return self._profiles.get(name)

    def get_policy(self, name: str) -> Optional[ToolPolicy]:
        return self._policies.get(name)

    def list_profiles(self) -> List[ToolProfile]:
        return list(self._profiles.values())

    def set_default_profile(self, name: str):
        if name in self._profiles:
            self._default_profile = name

    def filter_tools(
        self,
        tool_names: List[str],
        profile_name: Optional[str] = None,
        extra_allow: Optional[List[str]] = None,
        extra_deny: Optional[List[str]] = None,
        is_owner: bool = True,
    ) -> Set[str]:
        """
        Filter tools through policy pipeline
        References OpenClaw's tool-policy-pipeline.ts
        """
        profile_name = profile_name or self._default_profile
        policy = self.get_policy(profile_name)

        if not policy:
            policy = ToolPolicy()

        allowed = set()

        for name in tool_names:
            name_lower = name.lower()

            if not policy.is_allowed(name_lower):
                continue

            if policy.needs_owner(name_lower) and not is_owner:
                continue

            allowed.add(name)

        if extra_allow:
            allowed.update(extra_allow)

        if extra_deny:
            allowed.difference_update(extra_deny)

        return allowed

    def check_approval(
        self,
        tool_name: str,
        profile_name: Optional[str] = None,
    ) -> bool:
        """Check if tool needs approval"""
        profile_name = profile_name or self._default_profile
        policy = self.get_policy(profile_name)
        if not policy:
            return False
        return policy.needs_approval(tool_name)


class ToolPolicyPipeline:
    """
    Policy pipeline with multiple layers
    References OpenClaw's tool-policy-pipeline.ts
    """

    def __init__(self):
        self._layers: List[Callable[[str], Optional[bool]]] = []

    def add_layer(self, layer: Callable[[str], Optional[bool]):
        self._layers.append(layer)

    def evaluate(self, tool_name: str) -> bool:
        for layer in self._layers:
            result = layer(tool_name)
            if result is not None:
                return result
        return True


def create_path_policy(
    allowed_paths: Optional[List[str]],
    denied_paths: Optional[List[str]],
) -> Callable[[str], Optional[bool]]:
    """Create path-based policy layer"""
    def policy(tool_name: str) -> Optional[bool]:
        return None
    return policy


def create_sandbox_policy(
    sandbox_enabled: bool,
) -> Callable[[str], Optional[bool]]:
    """Create sandbox policy layer"""
    def policy(tool_name: str) -> Optional[bool]:
        return None
    return policy
