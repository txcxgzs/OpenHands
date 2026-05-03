"""
Example: Windows Automation
"""

import asyncio
from auroraagent import EmbeddedAgent, AgentConfig


async def main():
    config = AgentConfig.load()
    agent = EmbeddedAgent(config)
    await agent.initialize()

    session_id = await agent.create_session(tool_profile="full")

    print("Starting Windows automation demo...")

    await agent.queue_message(
        session_id,
        """Please perform the following Windows automation tasks:
        1. Get the screen size
        2. Take a screenshot
        3. Report the results
        """
    )

    result = await agent.run(session_id, max_iterations=5)
    print(f"\nAutomation result:\n{result.final_answer}")


if __name__ == "__main__":
    asyncio.run(main())
