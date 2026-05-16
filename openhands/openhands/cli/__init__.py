"""
OpenHands CLI - 命令行入口
"""

import asyncio
import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="OpenHands - AI Assistant That Grows With You",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("prompt", nargs="?", help="直接提问")
    parser.add_argument("--setup", "-s", action="store_true", help="配置向导")
    parser.add_argument("--gui", "-g", action="store_true", help="启动 Web GUI")
    parser.add_argument("--model", "-m", help="指定模型")
    parser.add_argument("--provider", "-p", help="指定提供商")
    parser.add_argument("--list-providers", "-l", action="store_true", help="列出提供商")
    parser.add_argument("--status", action="store_true", help="显示状态")
    parser.add_argument("--version", "-v", action="store_true", help="显示版本")
    
    args = parser.parse_args()
    
    if args.version:
        from openhands import __version__
        print(f"OpenHands v{__version__}")
        return
    
    if args.setup:
        from openhands.config_manager import quick_setup
        quick_setup()
        return
    
    if args.list_providers:
        from openhands.config_manager import config_manager, MODEL_PROVIDERS
        print("\n可用的模型提供商:")
        for provider_id, provider in MODEL_PROVIDERS.items():
            status = "✓" if config_manager.get(provider.env_key) or not provider.env_key else "✗"
            print(f"  {status} {provider.name}: {provider.description}")
        return
    
    if args.status:
        from openhands.config_manager import config_manager
        print("\n配置状态:")
        status = config_manager.get_provider_status()
        for pid, info in status.items():
            s = "✓" if info["configured"] else "✗"
            print(f"  {s} {info['name']}")
        print(f"\n默认模型: {config_manager.get_default_model()}")
        return
    
    if args.gui:
        from openhands.gui.server import run_gui
        run_gui()
        return
    
    # 交互式对话
    async def run_chat():
        from openhands import EmbeddedAgent, AgentConfig, ModelConfig
        from openhands.config_manager import config_manager
        
        default_model = config_manager.get_default_model()
        if "/" in default_model:
            provider, model = default_model.split("/", 1)
        else:
            provider, model = "openai", default_model
        
        if args.provider:
            provider = args.provider
        if args.model:
            model = args.model
        
        api_key = config_manager.get_api_key(provider)
        
        print(f"\nOpenHands - AI Assistant")
        print(f"模型: {provider}/{model}")
        print("输入 'quit' 退出\n")
        
        config = AgentConfig(model=ModelConfig(provider=provider, model=model, api_key=api_key))
        agent = EmbeddedAgent(config)
        await agent.initialize()
        
        if args.prompt:
            print(f"用户: {args.prompt}")
            session_id = await agent.create_session()
            await agent.queue_message(session_id, args.prompt)
            result = await agent.run(session_id)
            print(f"\n助手: {result.final_answer}\n")
            return
        
        session_id = await agent.create_session()
        while True:
            try:
                user_input = input("用户: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ['quit', 'exit']:
                    break
                await agent.queue_message(session_id, user_input)
                result = await agent.run(session_id)
                print(f"\n助手: {result.final_answer}\n")
            except KeyboardInterrupt:
                break
    
    asyncio.run(run_chat())


if __name__ == "__main__":
    main()
