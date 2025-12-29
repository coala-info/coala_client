"""CLI interface for Coala Client."""

import asyncio
import json
from typing import Any

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.style import Style
from rich.text import Text

from .config import Config, create_default_mcp_config, load_config
from .llm_client import LLMClient
from .mcp_manager import MCPManager


console = Console()

# Styles
USER_STYLE = Style(color="cyan", bold=True)
ASSISTANT_STYLE = Style(color="green")
TOOL_STYLE = Style(color="yellow")
ERROR_STYLE = Style(color="red", bold=True)
INFO_STYLE = Style(color="blue")


def print_welcome() -> None:
    """Print welcome message."""
    console.print()
    console.print(
        Panel(
            "[bold cyan]Coala Client[/bold cyan] - LLM CLI with MCP Support\n"
            "[dim]Type '/help' for commands, '/exit' or Ctrl+C to quit[/dim]",
            border_style="cyan",
        )
    )
    console.print()


def print_help() -> None:
    """Print help message."""
    help_text = """
[bold]Available Commands:[/bold]
  [cyan]/help[/cyan]        - Show this help message
  [cyan]/exit[/cyan]        - Exit the chat
  [cyan]/clear[/cyan]       - Clear conversation history
  [cyan]/tools[/cyan]       - List available MCP tools
  [cyan]/servers[/cyan]     - List connected MCP servers
  [cyan]/model[/cyan]       - Show current model info
  [cyan]/switch <provider>[/cyan] - Switch provider (openai/gemini/ollama)

[bold]Chat:[/bold]
  Just type your message and press Enter to chat with the LLM.
  The assistant can use MCP tools when available.
"""
    console.print(help_text)


class ChatSession:
    """Interactive chat session."""

    def __init__(
        self,
        config: Config,
        mcp_manager: MCPManager | None = None,
    ) -> None:
        """Initialize the chat session.

        Args:
            config: Application configuration.
            mcp_manager: Optional MCP manager.
        """
        self.config = config
        self.mcp_manager = mcp_manager
        self.llm_client = LLMClient(config)
        self.llm_client.add_system_message(config.system_prompt)
        self._pending_tool_results: dict[str, str] = {}

    async def close(self) -> None:
        """Close the session and cleanup resources."""
        await self.llm_client.close()

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool and return the result.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            Tool result as string.
        """
        if not self.mcp_manager:
            return f"Error: No MCP servers connected"

        console.print(f"  [yellow]⚙ Calling tool:[/yellow] {name}")
        console.print(f"    [dim]Arguments: {json.dumps(arguments, indent=2)}[/dim]")

        result = await self.mcp_manager.call_tool(name, arguments)

        # Truncate long results for display
        display_result = result[:500] + "..." if len(result) > 500 else result
        console.print(f"    [dim]Result: {display_result}[/dim]")

        return result

    async def process_message(self, user_input: str) -> None:
        """Process a user message.

        Args:
            user_input: The user's input.
        """
        # Add user message to the conversation
        self.llm_client.add_user_message(user_input)

        # Get available tools
        tools = None
        if self.mcp_manager:
            tools = self.mcp_manager.get_openai_tools()

        console.print()
        console.print("[green]Coala:[/green] ", end="")

        full_response = ""
        tool_calls_made = False

        try:
            while True:
                async for chunk in self.llm_client._stream_response(tools):
                    full_response += chunk
                    console.print(chunk, end="", highlight=False)

                # Check for tool calls
                if self.llm_client._has_pending_tool_calls():
                    tool_calls_made = True
                    console.print()  # New line after any content
                    last_msg = self.llm_client.messages[-1]
                    tool_calls = last_msg.get("tool_calls", [])

                    for tool_call in tool_calls:
                        name = tool_call["function"]["name"]
                        try:
                            args = json.loads(tool_call["function"]["arguments"])
                        except json.JSONDecodeError:
                            args = {}

                        result = await self.execute_tool(name, args)
                        self.llm_client.add_tool_result(tool_call["id"], result)

                    # Continue the conversation
                    console.print("\n[green]Coala:[/green] ", end="")
                    full_response = ""
                else:
                    break

            console.print()  # Final newline

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")

    def switch_provider(self, provider: str) -> None:
        """Switch to a different LLM provider.

        Args:
            provider: Provider name.
        """
        try:
            self.config.provider = provider
            self.llm_client = LLMClient(self.config, provider)
            self.llm_client.add_system_message(self.config.system_prompt)
            console.print(f"[green]Switched to {provider}[/green]")
            self.show_model_info()
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")

    def show_model_info(self) -> None:
        """Show current model information."""
        provider_config = self.config.get_provider_config()
        console.print(f"[blue]Provider:[/blue] {self.config.provider}")
        console.print(f"[blue]Model:[/blue] {provider_config.model}")
        console.print(f"[blue]Base URL:[/blue] {provider_config.base_url}")

    def show_tools(self) -> None:
        """Show available MCP tools."""
        if not self.mcp_manager:
            console.print("[yellow]No MCP servers connected[/yellow]")
            return

        tools = self.mcp_manager.get_all_tools()
        if not tools:
            console.print("[yellow]No tools available[/yellow]")
            return

        console.print(f"[blue]Available tools ({len(tools)}):[/blue]")
        for tool in tools:
            console.print(f"  [cyan]{tool.name}[/cyan]: {tool.description or 'No description'}")

    def show_servers(self) -> None:
        """Show connected MCP servers."""
        if not self.mcp_manager:
            console.print("[yellow]No MCP servers connected[/yellow]")
            return

        if not self.mcp_manager.connections:
            console.print("[yellow]No servers connected[/yellow]")
            return

        console.print(f"[blue]Connected servers ({len(self.mcp_manager.connections)}):[/blue]")
        for name, connection in self.mcp_manager.connections.items():
            console.print(f"  [cyan]{name}[/cyan]: {len(connection.tools)} tools")

    async def run(self) -> None:
        """Run the interactive chat session."""
        print_welcome()
        self.show_model_info()

        if self.mcp_manager and self.mcp_manager.connections:
            console.print()
            self.show_servers()

        console.print()

        while True:
            try:
                user_input = Prompt.ask("[cyan]You[/cyan]")

                if not user_input.strip():
                    continue

                # Handle commands (prefixed with /)
                cmd = user_input.strip().lower()

                if cmd in ("/exit", "/quit", "/q", "exit", "quit", "q"):
                    console.print("[dim]Goodbye![/dim]")
                    return
                elif cmd == "/help":
                    print_help()
                    continue
                elif cmd == "/clear":
                    self.llm_client.reset_messages()
                    self.llm_client.add_system_message(self.config.system_prompt)
                    console.print("[green]Conversation cleared[/green]")
                    continue
                elif cmd == "/tools":
                    self.show_tools()
                    continue
                elif cmd == "/servers":
                    self.show_servers()
                    continue
                elif cmd == "/model":
                    self.show_model_info()
                    continue
                elif cmd.startswith("/switch "):
                    provider = cmd.split(" ", 1)[1].strip()
                    self.switch_provider(provider)
                    continue

                # Regular chat message
                await self.process_message(user_input)

            except KeyboardInterrupt:
                console.print("\n[dim]Goodbye![/dim]")
                return
            except EOFError:
                console.print("\n[dim]Goodbye![/dim]")
                return


async def run_chat(
    provider: str | None = None,
    model: str | None = None,
    no_mcp: bool = False,
) -> None:
    """Run the chat interface.

    Args:
        provider: LLM provider name.
        model: Model name override.
        no_mcp: If True, don't connect to MCP servers.
    """
    config = load_config()

    if provider:
        config.provider = provider

    if model:
        # Override model for current provider
        if config.provider == "openai":
            config.openai_model = model
        elif config.provider == "gemini":
            config.gemini_model = model
        elif config.provider == "ollama":
            config.ollama_model = model

    if not no_mcp:
        async with MCPManager(config) as manager:
            mcp_manager = None
            try:
                await manager.connect_all_servers()
                mcp_manager = manager
            except Exception as e:
                console.print(f"[yellow]Warning: Could not connect to MCP servers: {e}[/yellow]")

            session = ChatSession(config, mcp_manager)
            try:
                await session.run()
            finally:
                await session.close()
    else:
        session = ChatSession(config, None)
        try:
            await session.run()
        finally:
            await session.close()


async def run_single_prompt(
    prompt: str,
    provider: str | None = None,
    model: str | None = None,
    no_mcp: bool = False,
) -> None:
    """Run a single prompt and exit.

    Args:
        prompt: The prompt to send.
        provider: LLM provider name.
        model: Model name override.
        no_mcp: If True, don't connect to MCP servers.
    """
    config = load_config()

    if provider:
        config.provider = provider

    if model:
        if config.provider == "openai":
            config.openai_model = model
        elif config.provider == "gemini":
            config.gemini_model = model
        elif config.provider == "ollama":
            config.ollama_model = model

    async def run_with_mcp() -> None:
        async with MCPManager(config) as manager:
            try:
                await manager.connect_all_servers()
            except Exception:
                pass

            session = ChatSession(config, manager)
            try:
                await session.process_message(prompt)
            finally:
                await session.close()

    async def run_without_mcp() -> None:
        session = ChatSession(config, None)
        try:
            await session.process_message(prompt)
        finally:
            await session.close()

    if no_mcp:
        await run_without_mcp()
    else:
        await run_with_mcp()
