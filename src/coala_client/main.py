"""Main entry point for Coala Client CLI."""

import asyncio

import click

from .cli import run_chat, run_single_prompt
from .config import create_default_mcp_config


@click.group(invoke_without_command=True)
@click.option(
    "-p", "--provider",
    type=click.Choice(["openai", "gemini", "ollama", "custom"]),
    help="LLM provider to use",
)
@click.option(
    "-m", "--model",
    help="Model name to use (overrides config)",
)
@click.option(
    "--no-mcp",
    is_flag=True,
    help="Disable MCP server connections",
)
@click.option(
    "-c", "--command",
    "prompt",
    help="Run a single prompt and exit",
)
@click.pass_context
def cli(
    ctx: click.Context,
    provider: str | None,
    model: str | None,
    no_mcp: bool,
    prompt: str | None,
) -> None:
    """Coala Client - A simple CLI for LLM with MCP server support.

    Supports OpenAI-compatible APIs including OpenAI, Gemini, and Ollama.
    """
    if ctx.invoked_subcommand is not None:
        return

    if prompt:
        asyncio.run(run_single_prompt(prompt, provider, model, no_mcp))
    else:
        asyncio.run(run_chat(provider, model, no_mcp))


@cli.command()
def init() -> None:
    """Initialize configuration files."""
    create_default_mcp_config()
    click.echo("Created default configuration files:")
    click.echo("  - ~/.config/coala/mcp_servers.json")
    click.echo("  - ~/.config/coala/env")
    click.echo("\nTo get started:")
    click.echo("  1. Set your API key: export OPENAI_API_KEY=your-key")
    click.echo("  2. Edit MCP servers: ~/.config/coala/mcp_servers.json")
    click.echo("  3. Add environment variables: ~/.config/coala/env")
    click.echo("  4. Run: coala")


@cli.command()
@click.option(
    "-p", "--provider",
    type=click.Choice(["openai", "gemini", "ollama", "custom"]),
    help="LLM provider to use",
)
@click.option(
    "-m", "--model",
    help="Model name to use",
)
@click.option(
    "--no-mcp",
    is_flag=True,
    help="Disable MCP server connections",
)
def chat(provider: str | None, model: str | None, no_mcp: bool) -> None:
    """Start an interactive chat session."""
    asyncio.run(run_chat(provider, model, no_mcp))


@cli.command()
@click.argument("prompt")
@click.option(
    "-p", "--provider",
    type=click.Choice(["openai", "gemini", "ollama", "custom"]),
    help="LLM provider to use",
)
@click.option(
    "-m", "--model",
    help="Model name to use",
)
@click.option(
    "--no-mcp",
    is_flag=True,
    help="Disable MCP server connections",
)
def ask(prompt: str, provider: str | None, model: str | None, no_mcp: bool) -> None:
    """Send a single prompt and get a response."""
    asyncio.run(run_single_prompt(prompt, provider, model, no_mcp))


@cli.command()
def config() -> None:
    """Show current configuration."""
    from .config import load_config

    cfg = load_config()
    click.echo("Current Configuration:")
    click.echo(f"  Provider: {cfg.provider}")
    click.echo(f"  OpenAI Model: {cfg.openai_model}")
    click.echo(f"  Gemini Model: {cfg.gemini_model}")
    click.echo(f"  Ollama Model: {cfg.ollama_model}")
    click.echo(f"  MCP Config: {cfg.mcp_config_file}")

    click.echo("\nEnvironment Variables:")
    click.echo("  PROVIDER - Default provider (openai/gemini/ollama/custom)")
    click.echo("  OPENAI_API_KEY - OpenAI API key")
    click.echo("  OPENAI_MODEL - OpenAI model name")
    click.echo("  GEMINI_API_KEY - Gemini API key")
    click.echo("  GEMINI_MODEL - Gemini model name")
    click.echo("  OLLAMA_BASE_URL - Ollama base URL")
    click.echo("  OLLAMA_MODEL - Ollama model name")


if __name__ == "__main__":
    cli()
