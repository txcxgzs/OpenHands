"""
Example: Subagent Delegation
"""

import asyncio
from openhands import EmbeddedAgent, AgentConfig
from openhands.core.subagents import SubAgentManager


async def main():
    config = AgentConfig.load()
    agent = EmbeddedAgent(config)
    await agent.initialize()

    subagent_manager = SubAgentManager(agent)

    print("Available subagents:")
    for sa in subagent_manager.list_subagents():
        print(f"  - {sa.name}: {sa.description}")

    print("\nDelegating to coder subagent...")
    result = await subagent_manager.delegate(
        "coder",
        "Write a simple Python function to calculate fibonacci numbers"
    )
    print(f"Coder result:\n{result}")

    print("\nDelegating to researcher subagent...")
    result = await subagent_manager.delegate(
        "researcher",
        "Find the latest news about AI agents"
    )
    print(f"Researcher result:\n{result[:500]}...")


if __name__ == "__main__":
    asyncio.run(main())
