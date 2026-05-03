
"""
CLI Main Entry
"""

import asyncio
import logging
from typing import Optional
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug mode")
def main(debug: bool):
    """AuroraAgent - AI Assistant with Windows Control"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level)


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Config file path")
@click.option("--profile", "-p", default="coding", help="Tool profile")
def chat(config: Optional[str], profile: str):
    """Start interactive chat"""
    from auroraagent import EmbeddedAgent, AgentConfig

    async def run_chat():
        cfg = AgentConfig.load(config)
        agent = EmbeddedAgent(cfg)
        await agent.initialize()

        console.print(Panel.fit(
            "[bold green]AuroraAgent[/bold green]\n"
            f"Profile: {profile}\n"
            "Type 'exit' to quit",
            title="Welcome",
        ))

        session_id = await agent.create_session(tool_profile=profile)

        while True:
            try:
                user_input = console.input("[bold blue]You:[/bold blue] ")
                if user_input.lower() in ("exit", "quit", "q"):
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                await agent.queue_message(session_id, user_input)
                result = await agent.run(session_id)

                if result.final_answer:
                    console.print(Panel(
                        Markdown(result.final_answer),
                        title="[bold green]Aurora[/bold green]",
                    ))

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    asyncio.run(run_chat())


@main.command()
def tools():
    """List available tools"""
    from auroraagent import tool_registry

    registry = tool_registry()
    tools_list = registry.list_tools()

    console.print("[bold]Available Tools:[/bold]\n")
    for tool in tools_list:
        console.print(f"  • [cyan]{tool.name}[/cyan]: {tool.description}")


@main.command()
def profiles():
    """List tool profiles"""
    from auroraagent import ToolPolicyManager

    manager = ToolPolicyManager()
    profiles_list = manager.list_profiles()

    console.print("[bold]Tool Profiles:[/bold]\n")
    for p in profiles_list:
        console.print(f"  • [cyan]{p.name}[/cyan]: {p.description}")


@main.command()
@click.argument("prompt")
@click.option("--config", "-c", type=click.Path(), help="Config file path")
def ask(prompt: str, config: Optional[str]):
    """Ask a single question"""
    from auroraagent import EmbeddedAgent, AgentConfig

    async def run():
        cfg = AgentConfig.load(config)
        agent = EmbeddedAgent(cfg)
        await agent.initialize()

        session_id = await agent.create_session()
        await agent.queue_message(session_id, prompt)
        result = await agent.run(session_id)

        if result.final_answer:
            console.print(Markdown(result.final_answer))

    asyncio.run(run())


if __name__ == "__main__":
    main()
