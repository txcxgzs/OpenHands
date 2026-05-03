"""
AuroraAgent 简单使用示例
"""
import asyncio
from auroraagent import AuroraAgent, AgentConfig


async def main():
    # 加载配置
    config = AgentConfig.load()
    
    # 创建 Agent
    agent = AuroraAgent(config)
    await agent.initialize()
    
    print("=== AuroraAgent 示例 ===\n")
    
    # 发送消息
    result = await agent.chat(
        "你好，请帮我列出当前工作目录的内容"
    )
    
    print(f"最终回答:\n{result.final_answer}")
    print(f"\n使用了 {result.iteration_count} 次工具调用")


if __name__ == "__main__":
    asyncio.run(main())
