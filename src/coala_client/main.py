"""Main entry point for Coala Client CLI."""

import asyncio
import json
from pathlib import Path

import click

from .cli import run_chat, run_single_prompt
from .config import create_default_mcp_config, load_config
from .mcp_import import import_cwl_toolset
from .skill_import import SKILLS_DIR, import_skills


class _SourceType(click.ParamType):
    """Accept a local path or http(s) URL; only validate path existence for local paths."""

    name = "source"

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context) -> str:
        s = str(value).strip()
        if s.startswith("http://") or s.startswith("https://"):
            return s
        # Local path: validate existence
        path = Path(s)
        if not path.exists():
            self.fail(f"Path '{s}' does not exist.", param, ctx)
        return s


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
    "--sandbox",
    is_flag=True,
    help="Enable run_command tool so the LLM can run basic shell commands",
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
    sandbox: bool,
    prompt: str | None,
) -> None:
    """Coala Client - A simple CLI for LLM with MCP server support.

    Supports OpenAI-compatible APIs including OpenAI, Gemini, and Ollama.
    """
    if ctx.invoked_subcommand is not None:
        return

    if prompt:
        asyncio.run(run_single_prompt(prompt, provider, model, no_mcp, sandbox))
    else:
        asyncio.run(run_chat(provider, model, no_mcp, sandbox))


@cli.command()
def init() -> None:
    """Initialize configuration files."""
    create_default_mcp_config()
    click.echo("Created default configuration files:")
    click.echo("  - ~/.config/coala/mcps/mcp_servers.json")
    click.echo("  - ~/.config/coala/env")
    click.echo("\nTo get started:")
    click.echo("  1. Set your API key: export OPENAI_API_KEY=your-key")
    click.echo("  2. Edit MCP servers: ~/.config/coala/mcps/mcp_servers.json")
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
@click.option(
    "--sandbox",
    is_flag=True,
    help="Enable run_command tool so the LLM can run basic shell commands",
)
def chat(provider: str | None, model: str | None, no_mcp: bool, sandbox: bool) -> None:
    """Start an interactive chat session."""
    asyncio.run(run_chat(provider, model, no_mcp, sandbox))


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
@click.option(
    "--sandbox",
    is_flag=True,
    help="Enable run_command tool so the LLM can run basic shell commands",
)
def ask(prompt: str, provider: str | None, model: str | None, no_mcp: bool, sandbox: bool) -> None:
    """Send a single prompt and get a response."""
    asyncio.run(run_single_prompt(prompt, provider, model, no_mcp, sandbox))


@cli.command()
@click.argument("toolset")
@click.argument(
    "sources",
    nargs=-1,
    type=_SourceType(),
    required=True,
)
def mcp(toolset: str, sources: tuple[str, ...]) -> None:
    """Import CWL files or a zipped CWL archive as an MCP server.

    Copies or unzips SOURCES into ~/.config/coala/mcps/TOOLSET/, creates run_mcp.py,
    and adds the server to the MCP config. Returns the configuration.

    SOURCES: local paths or http(s) URLs to .cwl files or a .zip containing .cwl.
    """
    cfg = load_config()
    Path(cfg.mcp_config_file).expanduser().parent.mkdir(parents=True, exist_ok=True)
    try:
        entry = import_cwl_toolset(
            toolset,
            list(sources),
            mcp_config_file=cfg.mcp_config_file,
        )
    except (FileNotFoundError, ValueError, OSError) as e:
        click.echo(str(e), err=True)
        raise SystemExit(1) from e
    click.echo("MCP server added to ~/.config/coala/mcps/mcp_servers.json. Entry:")
    click.echo()
    click.echo(json.dumps({"mcpServers": {toolset: entry}}, indent=2))
    click.echo()
    click.echo(f"Toolset directory: ~/.config/coala/mcps/{toolset}/")
    click.echo("Script: run_mcp.py")


@cli.command()
@click.argument(
    "sources",
    nargs=-1,
    type=_SourceType(),
    required=True,
)
def skill(sources: tuple[str, ...]) -> None:
    """Import skills from a GitHub folder URL or a zip URL/path into ~/.config/coala/skills.

    SOURCES: GitHub tree URL (e.g. https://github.com/owner/repo/tree/main/skills),
    zip URL, or local zip/directory path.
    """
    try:
        skills_dir = import_skills(list(sources))
    except (FileNotFoundError, ValueError, OSError) as e:
        click.echo(str(e), err=True)
        raise SystemExit(1) from e
    click.echo(f"Skills imported to {skills_dir}")


@cli.command()
def config() -> None:
    """Show current configuration."""
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
