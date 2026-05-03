from typing import List, Set, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ToolPolicy:
    allow: Optional[List[str]] = None
    deny: Optional[List[str]] = None
    require_approval: Optional[List[str]] = None

    def is_allowed(self, tool_name: str) -> bool:
        tool_name = tool_name.lower()

        if self.deny and tool_name in [t.lower() for t in self.deny]:
            return False

        if self.allow:
            allow_lower = [t.lower() for t in self.allow]
            return tool_name in allow_lower

        return True

    def needs_approval(self, tool_name: str) -> bool:
        if not self.require_approval:
            return False
        return tool_name.lower() in [t.lower() for t in self.require_approval]


@dataclass
class ToolProfile:
    name: str
    policy: ToolPolicy
    description: str = ""


class ToolPolicyManager:
    def __init__(self):
        self._profiles: Dict[str, ToolProfile] = {}
        self._default_profile: Optional[str] = None
        self._init_default_profiles()

    def _init_default_profiles(self):
        self._profiles["minimal"] = ToolProfile(
            name="minimal",
            description="Minimal tools only",
            policy=ToolPolicy(allow=["read", "session_status"])
        )

        self._profiles["coding"] = ToolProfile(
            name="coding",
            description="Coding-focused tools",
            policy=ToolPolicy(
                allow=["read", "write", "edit", "exec", "terminal", "memory_search", "memory_get"]
            )
        )

        self._profiles["full"] = ToolProfile(
            name="full",
            description="All tools enabled",
            policy=ToolPolicy()
        )

        self._default_profile = "coding"

    def add_profile(self, profile: ToolProfile):
        self._profiles[profile.name] = profile

    def get_profile(self, name: str) -> Optional[ToolProfile]:
        return self._profiles.get(name)

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
        extra_deny: Optional[List[str]] = None
    ) -> Set[str]:
        profile_name = profile_name or self._default_profile
        profile = self.get_profile(profile_name)

        if not profile:
            return set(tool_names)

        allowed = set()
        for name in tool_names:
            if profile.policy.is_allowed(name):
                allowed.add(name)

        if extra_allow:
            allowed.update(extra_allow)

        if extra_deny:
            allowed.difference_update(extra_deny)

        return allowed
