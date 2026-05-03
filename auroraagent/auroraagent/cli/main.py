"""
AuroraAgent CLI - Main Entry Point
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

from rich.console import Console
from rich.logging import RichHandler

from auroraagent import AuroraAgent, AgentConfig

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """设置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(show_path=False, console=console)],
    )


def create_arg_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="AuroraAgent - Windows AI Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 配置 API Key
  # 设置环境变量:
  # set ANTHROPIC_API_KEY=sk-ant-xxx
  # 或在 config.yaml 中配置
  
  # 交互式聊天
  aurora chat
  
  # 单条消息
  aurora chat -m "帮我截个图并描述一下"
  
  # 包含图像
  aurora chat -m "分析这张图" --image screenshot.png
  
  # 列出可用工具
  aurora tools list
        """,
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志",
    )
    
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        help="指定配置文件路径",
    )
    
    subparsers = parser.add_subparsers(title="Commands", dest="command")
    
    # 聊天命令
    chat_parser = subparsers.add_parser(
        "chat",
        help="与 AI 聊天",
        description="启动交互式聊天",
    )
    chat_parser.add_argument(
        "-m", "--message",
        type=str,
        default=None,
        help="单条消息（非交互式）",
    )
    chat_parser.add_argument(
        "-i", "--image",
        type=str,
        action="append",
        default=[],
        help="包含图像（可多次添加）",
    )
    chat_parser.add_argument(
        "-n", "--no-history",
        action="store_true",
        help="不加载/保存会话历史",
    )
    
    # 工具命令
    tools_parser = subparsers.add_parser(
        "tools",
        help="工具相关命令",
    )
    tools_subparsers = tools_parser.add_subparsers(dest="tools_command")
    tools_subparsers.add_parser("list", help="列出可用工具")
    
    # 配置命令
    config_parser = subparsers.add_parser(
        "config",
        help="配置管理",
    )
    config_parser.add_argument("--init", action="store_true", help="初始化配置文件")
    config_parser.add_argument("--show", action="store_true", help="显示当前配置")
    
    return parser


async def chat_loop(
    config: AgentConfig,
    message: Optional[str] = None,
    images: Optional[list] = None,
    save_history: bool = True,
) -> None:
    """聊天循环"""
    agent = AuroraAgent(config)
    await agent.initialize()
    
    console.print("\n[bold cyan]╔═══ AuroraAgent ═══╗[/bold cyan]")
    console.print("[cyan]Type your request, or 'exit' to quit[/cyan]")
    console.print("[dim]---[/dim]\n")
    
    if message:
        # 单条消息模式
        with console.status("[bold blue]Thinking...[/bold blue]"):
            result = await agent.chat(message, images=images)
        
        console.print(f"[bold yellow]Aurora:[/bold yellow] {result.final_answer}")
        console.print(f"\n[dim]Tool calls: {result.iteration_count}[/dim]")
    else:
        # 交互式模式
        try:
            while True:
                user_input = console.input("[bold green]You:[/bold green] ").strip()
                
                if user_input.lower() in ("exit", "quit", "q"):
                    break
                
                if not user_input:
                    continue
                
                with console.status("[bold blue]Thinking...[/bold blue]"):
                    result = await agent.chat(user_input)
                
                console.print(f"\n[bold yellow]Aurora:[/bold yellow] {result.final_answer}")
                if result.iteration_count > 0:
                    console.print(f"\n[dim]Tool calls: {result.iteration_count}[/dim]")
                console.print()
        except KeyboardInterrupt:
            console.print("\n[dim]Keyboard interrupt. Exiting...[/dim]")


async def tools_list() -> None:
    """列出工具"""
    from auroraagent.tools import tool_registry
    from auroraagent.tools.file_tools import register_tools as reg_file
    from auroraagent.tools.terminal_tools import register_tools as reg_terminal
    
    registry = tool_registry()
    
    # 临时注册查看
    reg_file(registry)
    reg_terminal(registry)
    
    console.print("\n[bold cyan]Available Tools:[/bold cyan]\n")
    
    for name in sorted(registry.list_tools()):
        tool = registry.get(name)
        if tool:
            console.print(f"  [blue]{name}[/blue]: {tool.description}")
    
    console.print(f"\nTotal: {len(registry.list_tools())} tools\n")


async def config_commands(
    args_config: argparse.Namespace,
    config: AgentConfig,
) -> None:
    """处理配置命令"""
    if args_config.init:
        config_path = args_config.config or config._get_default_config_path()
        config.save(config_path)
        console.print(f"[green]Config created at:[/green] {config_path}")
    elif args_config.show:
        import json
        from dataclasses import asdict
        
        config_dict = asdict(config)
        del config_dict["home_dir"]
        
        console.print("\n[bold cyan]Configuration:[/bold cyan]\n")
        console.print_json(json.dumps(config_dict, indent=2))


def main(argv: Optional[Sequence[str]] = None) -> int:
    """主入口"""
    argv = argv or sys.argv[1:]
    parser = create_arg_parser()
    args = parser.parse_args(argv)
    
    setup_logging(args.verbose)
    
    config = AgentConfig.load(args.config)
    
    if args.command == "chat":
        asyncio.run(
            chat_loop(
                config,
                message=args.message,
                images=args.image,
                save_history=not args.no_history,
            )
        )
    elif args.command == "tools" and args.tools_command == "list":
        asyncio.run(tools_list())
    elif args.command == "config":
        asyncio.run(config_commands(args, config))
    else:
        parser.print_help()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
