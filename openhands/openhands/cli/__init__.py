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
        epilog="""
示例:
  openhands                    # 启动交互式对话
  openhands "帮我写一个脚本"   # 直接提问
  openhands --setup            # 配置 API Key
  openhands --gui              # 启动 Web 界面
  openhands --model gpt-4      # 指定模型
        """,
    )
    
    parser.add_argument(
        "prompt",
        nargs="?",
        help="直接提问 (可选)",
    )
    
    parser.add_argument(
        "--setup", "-s",
        action="store_true",
        help="运行配置向导",
    )
    
    parser.add_argument(
        "--gui", "-g",
        action="store_true",
        help="启动 Web GUI",
    )
    
    parser.add_argument(
        "--model", "-m",
        help="指定模型 (例如: gpt-4, claude-3-opus)",
    )
    
    parser.add_argument(
        "--provider", "-p",
        help="指定提供商 (例如: openai, anthropic, longcat)",
    )
    
    parser.add_argument(
        "--list-providers", "-l",
        action="store_true",
        help="列出所有模型提供商",
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="显示配置状态",
    )
    
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="显示版本",
    )
    
    args = parser.parse_args()
    
    # 版本
    if args.version:
        from openhands import __version__
        print(f"OpenHands v{__version__}")
        return
    
    # 配置向导
    if args.setup:
        from openhands.config_manager import quick_setup
        quick_setup()
        return
    
    # 列出提供商
    if args.list_providers:
        from openhands.config_manager import config_manager, MODEL_PROVIDERS
        print("\n可用的模型提供商:")
        print("-" * 50)
        for provider_id, provider in MODEL_PROVIDERS.items():
            status = "✓ 已配置" if config_manager.get(provider.env_key) or not provider.env_key else "✗ 未配置"
            print(f"  {provider.name:15} {provider.description:30} [{status}]")
        print()
        return
    
    # 显示状态
    if args.status:
        from openhands.config_manager import config_manager
        print("\nOpenHands 配置状态:")
        print("-" * 50)
        status = config_manager.get_provider_status()
        for provider_id, info in status.items():
            status_text = "✓" if info["configured"] else "✗"
            print(f"  {status_text} {info['name']:15} {info['description']}")
        print(f"\n默认模型: {config_manager.get_default_model()}")
        print()
        return
    
    # 启动 GUI
    if args.gui:
        import subprocess
        import webbrowser
        import time
        import threading
        
        port = int(config_manager.get("GUI_PORT", "8000"))
        
        def open_browser():
            time.sleep(2)
            webbrowser.open(f"http://localhost:{port}")
        
        threading.Thread(target=open_browser, daemon=True).start()
        
        print(f"\n启动 OpenHands Web GUI...")
        print(f"访问地址: http://localhost:{port}")
        print("按 Ctrl+C 停止\n")
        
        subprocess.run([
            sys.executable, "-m", "openhands.gui.server"
        ])
        return
    
    # 交互式对话
    async def run_chat():
        from openhands import EmbeddedAgent, AgentConfig, ModelConfig
        from openhands.config_manager import config_manager
        
        # 获取模型配置
        default_model = config_manager.get_default_model()
        if "/" in default_model:
            provider, model = default_model.split("/", 1)
        else:
            provider = "openai"
            model = default_model
        
        if args.provider:
            provider = args.provider
        if args.model:
            model = args.model
        
        # 获取 API Key
        api_key = config_manager.get_api_key(provider)
        
        print(f"\nOpenHands - AI Assistant")
        print(f"模型: {provider}/{model}")
        print("输入 'quit' 或 'exit' 退出, 'help' 查看帮助\n")
        
        # 创建 Agent
        config = AgentConfig(
            model=ModelConfig(
                provider=provider,
                model=model,
                api_key=api_key,
            )
        )
        
        agent = EmbeddedAgent(config)
        await agent.initialize()
        
        # 如果有直接提问
        if args.prompt:
            print(f"用户: {args.prompt}")
            session_id = await agent.create_session()
            await agent.queue_message(session_id, args.prompt)
            result = await agent.run(session_id)
            print(f"\n助手: {result.final_answer}\n")
            return
        
        # 交互式对话
        session_id = await agent.create_session()
        
        while True:
            try:
                user_input = input("用户: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit']:
                    print("\n再见!")
                    break
                
                if user_input.lower() == 'help':
                    print("\n命令:")
                    print("  help  - 显示帮助")
                    print("  clear - 清除对话历史")
                    print("  stats - 显示统计信息")
                    print("  quit  - 退出")
                    print()
                    continue
                
                if user_input.lower() == 'clear':
                    agent.clear_history()
                    print("对话历史已清除\n")
                    continue
                
                if user_input.lower() == 'stats':
                    stats = agent.get_stats()
                    print(f"\n统计信息:")
                    print(f"  会话数: {stats.get('sessions', 0)}")
                    print(f"  工具调用: {stats.get('tool_calls', 0)}")
                    print()
                    continue
                
                # 发送消息
                await agent.queue_message(session_id, user_input)
                result = await agent.run(session_id)
                
                print(f"\n助手: {result.final_answer}\n")
                
            except KeyboardInterrupt:
                print("\n\n再见!")
                break
            except Exception as e:
                print(f"\n错误: {e}\n")
    
    asyncio.run(run_chat())


if __name__ == "__main__":
    main()
