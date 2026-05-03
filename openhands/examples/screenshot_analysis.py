"""
Example: Screenshot Analysis
"""

import asyncio
from pathlib import Path
from openhands import EmbeddedAgent, AgentConfig


async def main():
    config = AgentConfig.load()
    agent = EmbeddedAgent(config)
    await agent.initialize()

    session_id = await agent.create_session()

    screenshot_path = Path("./data/screenshots/screenshot.png")
    if screenshot_path.exists():
        print("Analyzing screenshot...")
        await agent.queue_message(
            session_id,
            "Analyze this screenshot and describe what you see.",
            images=[str(screenshot_path)],
        )
    else:
        await agent.queue_message(
            session_id,
            "Take a screenshot and analyze the screen.",
        )

    result = await agent.run(session_id)
    print(f"\nAnalysis:\n{result.final_answer}")


if __name__ == "__main__":
    asyncio.run(main())
