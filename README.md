# Coala Client

A simple command line interface for LLM with MCP (Model Context Protocol) server support and OpenAI-compatible API support.

## Features

- **OpenAI-compatible API support**: Works with OpenAI, Google Gemini, Ollama, and any OpenAI-compatible API
- **MCP Server integration**: Connect to multiple MCP servers for extended tool capabilities
- **Interactive chat**: Rich terminal UI with streaming responses
- **Tool calling**: Automatic tool execution with MCP servers

## Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

## Quick Start

### 1. Initialize Configuration

```bash
coala init
```

This creates a default MCP servers configuration file at `~/.config/coala/mcp_servers.json`.

### 2. Set API Key

```bash
# For OpenAI
export OPENAI_API_KEY=your-openai-api-key

# For Gemini
export GEMINI_API_KEY=your-gemini-api-key

# Ollama doesn't require an API key (runs locally)
```

### 3. Start Chatting

```bash
# Interactive chat with default provider (OpenAI)
coala

# Use a specific provider
coala -p gemini
coala -p ollama

# Use a specific model
coala -p openai -m gpt-4-turbo

# Single prompt
coala ask "What is the capital of France?"

# Disable MCP servers
coala --no-mcp
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROVIDER` | Default LLM provider | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `OPENAI_BASE_URL` | OpenAI base URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | OpenAI model | `gpt-4o` |
| `GEMINI_API_KEY` | Gemini API key | - |
| `GEMINI_BASE_URL` | Gemini base URL | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `GEMINI_MODEL` | Gemini model | `gemini-2.0-flash-exp` |
| `OLLAMA_BASE_URL` | Ollama base URL | `http://localhost:11434/v1` |
| `OLLAMA_MODEL` | Ollama model | `llama3.2` |
| `SYSTEM_PROMPT` | System prompt | `You are a helpful assistant.` |
| `MAX_TOKENS` | Max tokens in response | `4096` |
| `TEMPERATURE` | Temperature | `0.7` |
| `MCP_CONFIG_FILE` | MCP config file path | `~/.config/coala/mcp_servers.json` |

### MCP Servers Configuration

Edit `~/.config/coala/mcp_servers.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
      "env": {}
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your-token"
      }
    }
  }
}
```

### Environment Variables for MCP Servers

You can set environment variables that will be available to all MCP servers by editing `~/.config/coala/env`:

```bash
# Environment variables for MCP servers
# Format: KEY=value

# Set default provider (openai, gemini, ollama, custom)
PROVIDER=gemini

# API keys and model settings
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash-exp
```

**Note:** The `PROVIDER` variable in the env file will set the default LLM provider. These variables will be merged with server-specific `env` settings in `mcp_servers.json`. Server-specific environment variables take precedence over the base environment variables.

## CLI Commands

### Interactive Chat

```bash
coala [OPTIONS]
coala chat [OPTIONS]
```

Options:
- `-p, --provider`: LLM provider (openai/gemini/ollama/custom)
- `-m, --model`: Model name override
- `--no-mcp`: Disable MCP servers

### Single Prompt

```bash
coala ask "Your prompt here"
coala -c "Your prompt here"
```

### Chat Commands

During interactive chat:
- `/help` - Show help
- `/exit` / `/quit` - Exit chat
- `/clear` - Clear conversation history
- `/tools` - List available MCP tools
- `/servers` - List connected MCP servers
- `/model` - Show current model info
- `/switch <provider>` - Switch provider

### Configuration

```bash
coala init    # Create default config files
coala config  # Show current configuration
```

## Examples

### Using with Ollama

```bash
# Start Ollama server
ollama serve

# Pull a model
ollama pull llama3.2

# Chat with Ollama
coala -p ollama -m llama3.2
```

### Using with Gemini

```bash
export GEMINI_API_KEY=your-api-key
coala -p gemini
```

### Using Custom OpenAI-compatible API

```bash
export CUSTOM_API_KEY=your-api-key
export CUSTOM_BASE_URL=https://your-api.com/v1
export CUSTOM_MODEL=your-model
coala -p custom
```

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT
