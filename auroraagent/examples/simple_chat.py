"""
Example: Simple Chat Usage
"""

import asyncio
from auroraagent import EmbeddedAgent, AgentConfig


async def main():
    config = AgentConfig.load()
    agent = EmbeddedAgent(config)
    await agent.initialize()

    print("AuroraAgent initialized!")
    print(f"Available adapters: {agent._adapter.__class__.__name__}")

    session_id = await agent.create_session(tool_profile="coding")
    print(f"Session created: {session_id}")

    await agent.queue_message(session_id, "Hello! What can you do?")

    result = await agent.run(session_id)

    print(f"\nIterations: {result.meta.iteration_count}")
    print(f"Final Answer:\n{result.final_answer}")


if __name__ == "__main__":
    asyncio.run(main())
