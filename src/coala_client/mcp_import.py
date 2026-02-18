"""Import CWL toolsets and register them as MCP servers."""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen


def _is_url(source: str | Path) -> bool:
    if not isinstance(source, str):
        return False
    return source.startswith("http://") or source.startswith("https://")


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path or ""
    name = path.rsplit("/", 1)[-1] if path else ""
    return name or "download"


def _resolve_sources(sources: list[str | Path]) -> tuple[list[Path], tempfile.TemporaryDirectory | None]:
    """Resolve sources to local paths; download URLs to a temp dir. Returns (paths, temp_dir or None)."""
    resolved: list[Path] = []
    temp_dir: tempfile.TemporaryDirectory | None = None
    for src in sources:
        if _is_url(src):
            url = str(src)
            name = _filename_from_url(url)
            if not name.lower().endswith((".cwl", ".zip")):
                name += ".cwl"  # default for URLs with no extension
            if temp_dir is None:
                temp_dir = tempfile.TemporaryDirectory()
            dest = Path(temp_dir.name) / name
            with urlopen(url) as resp:
                dest.write_bytes(resp.read())
            resolved.append(dest)
        else:
            resolved.append(Path(src).resolve())
    return resolved, temp_dir


def _ensure_mcps_dir() -> Path:
    """Return ~/.config/coala/mcps/ (MCP config and toolsets)."""
    mcps_dir = Path("~/.config/coala/mcps").expanduser()
    mcps_dir.mkdir(parents=True, exist_ok=True)
    return mcps_dir


def _copy_cwl_sources(sources: list[Path], dest_dir: Path) -> list[Path]:
    """Copy CWL files into dest_dir. Returns paths to copied .cwl files in dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in sources:
        src = src.resolve()
        if not src.exists():
            raise FileNotFoundError(f"CWL file or archive not found: {src}")
        if src.suffix.lower() == ".zip":
            with zipfile.ZipFile(src) as zf:
                zf.extractall(dest_dir)
        else:
            if src.suffix.lower() != ".cwl":
                raise ValueError(f"Not a CWL file: {src}")
            shutil.copy2(src, dest_dir / src.name)
    # Include .cwl files in any subdirectory (e.g. from zip with nested dirs)
    cwl_paths = sorted(
        p for p in dest_dir.rglob("*")
        if p.is_file() and p.suffix.lower() == ".cwl"
    )
    return cwl_paths


def _generate_mcp_py(toolset_dir: Path, cwl_paths: list[Path]) -> str:
    """Generate run_mcp.py script content that loads all CWL tools and serves via stdio."""
    # Use paths relative to toolset_dir so nested dirs (e.g. from zip) work
    rel_paths = [p.relative_to(toolset_dir).as_posix() for p in sorted(cwl_paths)]
    add_lines = "\n".join(
        f'mcp.add_tool(os.path.join(base_dir, {repr(rel)}))'
        for rel in rel_paths
    )
    return f'''from coala.mcp_api import mcp_api
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
mcp = mcp_api()
{add_lines}
mcp.serve()
'''


def _load_mcp_servers_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {"mcpServers": {}}
    with open(config_path) as f:
        return json.load(f)


def _save_mcp_servers_config(config_path: Path, data: dict[str, Any]) -> None:
    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


def import_cwl_toolset(
    toolset: str,
    sources: list[str | Path],
    *,
    mcp_config_file: str = "~/.config/coala/mcps/mcp_servers.json",
) -> dict[str, Any]:
    """Import CWL files or a zip of CWL files into a named toolset and register as MCP server.

    Sources can be local paths or http(s) URLs to .cwl files or a .zip archive.

    - Copies or unzips sources into ~/.config/coala/<toolset>/
    - Creates run_mcp.py there (uses coala.mcp_api)
    - Adds or updates the toolset entry in mcp_servers.json
    - Returns the MCP server entry that was added (for display).

    Raises:
        FileNotFoundError: If any local source path does not exist.
        ValueError: If a non-zip source is not a .cwl file.
    """
    mcps_dir = _ensure_mcps_dir()
    toolset_dir = mcps_dir / toolset

    resolved, temp_dir = _resolve_sources(sources)
    try:
        # Single zip: treat as archive; otherwise treat as list of CWL files
        if len(resolved) == 1 and resolved[0].suffix.lower() == ".zip":
            # Remove existing content so unzip replaces cleanly
            if toolset_dir.exists():
                shutil.rmtree(toolset_dir)
            cwl_paths = _copy_cwl_sources(resolved, toolset_dir)
        else:
            # Ensure only .cwl files; replace existing .cwl in toolset dir
            for s in resolved:
                if s.suffix.lower() != ".cwl":
                    raise ValueError(f"Expected .cwl file or single .zip archive: {s}")
            if toolset_dir.exists():
                for f in toolset_dir.glob("*.cwl"):
                    f.unlink()
            cwl_paths = _copy_cwl_sources(resolved, toolset_dir)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    if not cwl_paths:
        raise ValueError(
            "No .cwl files found. Provide .cwl files or a .zip containing .cwl files."
        )

    # Use run_mcp.py to avoid shadowing the 'mcp' package (from mcp.server.fastmcp)
    mcp_py_path = toolset_dir / "run_mcp.py"
    mcp_py_path.write_text(_generate_mcp_py(toolset_dir, cwl_paths))

    config_path = Path(mcp_config_file).expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_mcp_servers_config(config_path)
    servers = data.setdefault("mcpServers", {})

    # Use absolute path so MCP client can run from any cwd
    mcp_py_abs = str(mcp_py_path.resolve())
    server_entry = {
        "command": "python",
        "args": [mcp_py_abs],
        "env": {},
    }
    servers[toolset] = server_entry
    _save_mcp_servers_config(config_path, data)

    return server_entry
