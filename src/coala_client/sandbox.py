"""Sandbox for running basic Linux commands invoked by the LLM."""

import subprocess
from pathlib import Path

from openai.types.chat import ChatCompletionToolParam

SANDBOX_TOOL_NAME = "run_command"
DEFAULT_TIMEOUT = 30


def run_sandbox_command(
    command: str,
    timeout: int = DEFAULT_TIMEOUT,
    cwd: str | Path | None = None,
) -> str:
    """Run a single shell command in a subprocess with timeout. Returns combined stdout and stderr."""
    if not command or not command.strip():
        return "Error: empty command"
    cwd_path = Path(cwd).expanduser().resolve() if cwd else None
    if cwd_path and not cwd_path.is_dir():
        return f"Error: cwd is not a directory: {cwd_path}"
    try:
        result = subprocess.run(
            command.strip(),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd_path,
        )
        out = result.stdout or ""
        err = result.stderr or ""
        if result.returncode != 0:
            return f"exit code {result.returncode}\n{out}\n{err}".strip() or f"exit code {result.returncode}"
        return out.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error: {e}"


def get_sandbox_tool() -> ChatCompletionToolParam:
    """Return the sandbox run_command tool in OpenAI tool format."""
    return {
        "type": "function",
        "function": {
            "name": SANDBOX_TOOL_NAME,
            "description": "Run a single basic Linux shell command. Use for reading files, listing dirs, grep, etc. No interactive or long-running commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run (e.g. 'ls -la', 'cat file.txt').",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 30).",
                        "default": DEFAULT_TIMEOUT,
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (optional).",
                    },
                },
                "required": ["command"],
            },
        },
    }
