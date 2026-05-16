
"""
SubAgent System - References OpenClaw's subagent architecture
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import logging

from ..types import Message, MessageRole
from ..config import AgentConfig
from ..agent.runner import EmbeddedAgent

logger = logging.getLogger(__name__)


@dataclass
class SubAgentConfig:
    """Sub-agent configuration"""
    name: str
    description: str
    system_prompt: str
    tool_profile: str = "coding"
    max_iterations: int = 10


class SubAgentManager:
    """
    Manages sub-agents for delegation
    References OpenClaw's subagent system
    """

    def __init__(self, parent_agent: EmbeddedAgent):
        self.parent = parent_agent
        self._sub_agents: Dict[str, SubAgentConfig] = {}
        self._init_default_subagents()

    def _init_default_subagents(self):
        self._sub_agents["coder"] = SubAgentConfig(
            name="coder",
            description="Specialized for coding tasks",
            system_prompt="You are a coding specialist. Focus on writing clean, efficient code.",
            tool_profile="coding",
            max_iterations=15,
        )

        self._sub_agents["researcher"] = SubAgentConfig(
            name="researcher",
            description="Specialized for research and information gathering",
            system_prompt="You are a research specialist. Gather and synthesize information.",
            tool_profile="minimal",
            max_iterations=10,
        )

        self._sub_agents["executor"] = SubAgentConfig(
            name="executor",
            description="Specialized for executing commands and operations",
            system_prompt="You are an execution specialist. Run commands safely and report results.",
            tool_profile="full",
            max_iterations=5,
        )

    def register_subagent(self, config: SubAgentConfig):
        self._sub_agents[config.name] = config

    def list_subagents(self) -> List[SubAgentConfig]:
        return list(self._sub_agents.values())

    def get_subagent(self, name: str) -> Optional[SubAgentConfig]:
        return self._sub_agents.get(name)

    async def delegate(
        self,
        subagent_name: str,
        task: str,
        context: Optional[List[Message]] = None,
    ) -> str:
        """Delegate task to sub-agent"""
        config = self.get_subagent(subagent_name)
        if not config:
            return f"Unknown sub-agent: {subagent_name}"

        session_id = await self.parent.create_session(
            tool_profile=config.tool_profile,
            metadata={"subagent": subagent_name},
        )

        if context:
            for msg in context[-5:]:
                self.parent.get_session(session_id).messages.append(msg)

        await self.parent.queue_message(session_id, task)

        result = await self.parent.run(
            session_id,
            max_iterations=config.max_iterations,
            system_prompt_override=config.system_prompt,
        )

        return result.final_answer or "No response from sub-agent"
