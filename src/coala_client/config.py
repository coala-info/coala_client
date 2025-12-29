"""Configuration module for Coala Client."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    api_key: str = ""
    base_url: str = ""
    model: str = ""


class Config(BaseSettings):
    """Main configuration class."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Default provider
    provider: str = "openai"

    # Provider configurations
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_model: str = "gemini-2.0-flash-exp"

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2"

    # Custom provider
    custom_api_key: str = ""
    custom_base_url: str = ""
    custom_model: str = ""

    # MCP servers config file path
    mcp_config_file: str = "~/.config/coala/mcp_servers.json"
    # Environment variables file path
    env_file: str = "~/.config/coala/env"

    # Chat settings
    system_prompt: str = "You are a helpful assistant."
    max_tokens: int = 4096
    temperature: float = 0.7

    def get_provider_config(self, provider: str | None = None) -> LLMProviderConfig:
        """Get configuration for a specific provider."""
        provider = provider or self.provider

        if provider == "openai":
            return LLMProviderConfig(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url,
                model=self.openai_model,
            )
        elif provider == "gemini":
            return LLMProviderConfig(
                api_key=self.gemini_api_key,
                base_url=self.gemini_base_url,
                model=self.gemini_model,
            )
        elif provider == "ollama":
            return LLMProviderConfig(
                api_key="ollama",  # Ollama doesn't need a real API key
                base_url=self.ollama_base_url,
                model=self.ollama_model,
            )
        elif provider == "custom":
            return LLMProviderConfig(
                api_key=self.custom_api_key,
                base_url=self.custom_base_url,
                model=self.custom_model,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def get_base_env(self) -> dict[str, str]:
        """Load base environment variables from env file."""
        env_path = Path(self.env_file).expanduser()
        if not env_path.exists():
            return {}

        env_vars: dict[str, str] = {}
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Parse key=value format
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    env_vars[key] = value
        return env_vars

    def get_mcp_servers(self) -> dict[str, MCPServerConfig]:
        """Load MCP server configurations from file."""
        config_path = Path(self.mcp_config_file).expanduser()
        if not config_path.exists():
            return {}

        with open(config_path) as f:
            data = json.load(f)

        # Get base environment variables
        base_env = self.get_base_env()

        servers = {}
        for name, config in data.get("mcpServers", {}).items():
            server_config = MCPServerConfig(**config)
            # Merge base env with server-specific env (server-specific takes precedence)
            merged_env = {**base_env, **server_config.env}
            server_config.env = merged_env
            servers[name] = server_config
        return servers


def load_env_file(env_file: str | None = None) -> None:
    """Load environment variables from env file and set them in os.environ.
    
    Args:
        env_file: Path to the environment file. If None, uses ENV_FILE
                  environment variable or default ~/.config/coala/env
    """
    if env_file is None:
        env_file = os.environ.get("ENV_FILE", "~/.config/coala/env")
    
    env_path = Path(env_file).expanduser()
    if not env_path.exists():
        return

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Parse key=value format
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                # Set the environment variable (env file values take precedence)
                if key:
                    os.environ[key] = value


def load_config() -> Config:
    """Load configuration from environment and files.
    
    Note: This function loads the env file, which will override
    system environment variables. The env file is loaded before
    creating Config to ensure its values take precedence.
    """
    # Load env file - this will override any existing environment variables
    # to ensure user's explicit configuration in the file takes precedence
    load_env_file()
    return Config()


def create_default_mcp_config() -> None:
    """Create default MCP servers configuration file and env file."""
    config_dir = Path("~/.config/coala").expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)

    # Create MCP servers config
    config_path = config_dir / "mcp_servers.json"
    if not config_path.exists():
        default_config: dict[str, Any] = {
            "mcpServers": {
                "example": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-everything"],
                    "env": {},
                }
            }
        }
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)

    # Create example env file
    env_path = config_dir / "env"
    if not env_path.exists():
        with open(env_path, "w") as f:
            f.write("# Environment variables for MCP servers\n")
            f.write("# Format: KEY=value\n")
            f.write("# These variables will be available to all MCP servers\n")
            f.write("# Server-specific env in mcp_servers.json will override these\n")
            f.write("\n")
            f.write("# Example:\n")
            f.write("# PROVIDER=gemini\n")
            f.write("# GEMINI_API_KEY=your-gemini-api-key\n")
            f.write("# GEMINI_MODEL=gemini-2.0-flash-exp\n")
