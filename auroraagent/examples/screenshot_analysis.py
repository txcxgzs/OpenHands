"""
截图分析示例
"""
import asyncio
from auroraagent import AuroraAgent, AgentConfig


async def main():
    config = AgentConfig.load()
    
    agent = AuroraAgent(config)
    await agent.initialize()
    
    print("=== 截图分析示例 ===\n")
    
    result = await agent.chat(
        "请先截图当前屏幕，然后告诉我你看到了什么"
    )
    
    print(f"分析结果:\n{result.final_answer}")


if __name__ == "__main__":
    asyncio.run(main())
