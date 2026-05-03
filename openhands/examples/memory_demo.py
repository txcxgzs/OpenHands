"""
Example: Memory Search
"""

import asyncio
from openhands import EmbeddedAgent, AgentConfig


async def main():
    config = AgentConfig.load()
    agent = EmbeddedAgent(config)
    await agent.initialize()

    session_id = await agent.create_session()

    await agent.queue_message(
        session_id,
        """Remember these facts:
        - My name is Alice
        - I prefer dark mode
        - I work as a software engineer
        """
    )

    result1 = await agent.run(session_id, max_iterations=2)
    print(f"Memory stored: {result1.final_answer}")

    await agent.queue_message(session_id, "What is my name and profession?")

    result2 = await agent.run(session_id)
    print(f"\nMemory recall:\n{result2.final_answer}")


if __name__ == "__main__":
    asyncio.run(main())
