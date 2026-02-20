# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-02-18

### Added

- OpenAI-compatible chat CLI (OpenAI, Gemini, Ollama, custom)
- MCP server integration: connect to multiple servers, tool calling in chat
- `coala init` — create default config at `~/.config/coala/mcps/`
- `coala` / `coala chat` — interactive chat; `coala ask "prompt"` — single prompt
- `coala mcp-import` (alias `coala mcp`) — import CWL files or zip as MCP toolset
- `coala mcp-list` — list servers; `coala mcp-list <server>` — list tool schemas
- `coala mcp-call <server>.<tool> --args '<JSON>'` — call MCP tool directly
- `coala skill` — import skills from GitHub tree URL or zip to `~/.config/coala/skills/`
- In-chat `/skill` and `/skill <name>` — list skills, load skill into context
- `--sandbox` — enable `run_command` tool for basic shell commands
- `--no-mcp` — disable MCP servers
- Options: `-p`/`--provider`, `-m`/`--model`
- Chat commands: `/help`, `/exit`, `/clear`, `/tools`, `/servers`, `/model`, `/switch`

[0.1.0]: https://github.com/coala-info/coala_client/releases/tag/v0.1.0
