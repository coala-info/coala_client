"""Import skills from URL or zip into ~/.config/coala/skills."""

import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


SKILLS_DIR = Path("~/.config/coala/skills").expanduser()


def list_skills() -> list[str]:
    """Return names of installed skills (subfolders under SKILLS_DIR)."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(
        p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def get_skill_content(name: str) -> str | None:
    """Load skill content from ~/.config/coala/skills/<name>/. Reads SKILL.md if present.

    Returns the skill text, or None if the skill folder or SKILL.md is missing.
    """
    skill_dir = SKILLS_DIR / name
    if not skill_dir.is_dir():
        return None
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        return skill_md.read_text(encoding="utf-8", errors="replace")
    # Fallback: first .md file in the folder
    for p in sorted(skill_dir.iterdir()):
        if p.suffix.lower() == ".md":
            return p.read_text(encoding="utf-8", errors="replace")
    return None


# GitHub tree URL: https://github.com/owner/repo/tree/branch/path
_GITHUB_TREE_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)(?:/(.*))?$",
    re.IGNORECASE,
)


def _folder_name_for_source(source: str | Path) -> str:
    """Return a subfolder name under skills/ for this source (e.g. bedtools)."""
    src_str = str(source).strip()
    if src_str.startswith("http://") or src_str.startswith("https://"):
        parsed = urlparse(src_str)
        path = (parsed.path or "").strip("/")
        segments = [s for s in path.split("/") if s]
        if len(segments) >= 2:
            # e.g. files/bedtools/bedtools-skills.zip -> bedtools
            return segments[-2]
        if segments:
            # e.g. bar.zip -> bar
            name = segments[-1]
            return Path(name).stem if "." in name else name
        return "skills"
    path = Path(source).resolve()
    if path.is_dir():
        return path.name
    return path.stem


def _is_url(source: str | Path) -> bool:
    if not isinstance(source, str):
        return False
    return source.startswith("http://") or source.startswith("https://")


def _parse_github_tree_url(url: str) -> tuple[str, str, str, str] | None:
    """Return (owner, repo, branch, path) or None if not a GitHub tree URL."""
    m = _GITHUB_TREE_RE.match(url.strip())
    if not m:
        return None
    owner, repo, branch, path = m.groups()
    path = (path or "").strip("/")
    return (owner, repo, branch, path)


def _download_github_folder(
    owner: str, repo: str, branch: str, folder: str, dest_dir: Path
) -> None:
    """Download repo archive and copy the specified folder contents into dest_dir."""
    archive_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
    with urlopen(archive_url) as resp:
        data = resp.read()
    prefix = f"{repo}-{branch}"
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "repo.zip"
        zip_path.write_bytes(data)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        extracted_top = Path(tmp) / prefix
        if not extracted_top.exists():
            for d in Path(tmp).iterdir():
                if d.is_dir():
                    extracted_top = d
                    break
        folder_path = extracted_top / folder if folder else extracted_top
        if not folder_path.exists():
            raise FileNotFoundError(
                f"Folder '{folder}' not found in {owner}/{repo} (branch {branch})"
            )
        dest_dir.mkdir(parents=True, exist_ok=True)
        for p in folder_path.iterdir():
            dest = dest_dir / p.name
            if dest.exists() and dest.is_dir() and p.is_dir():
                for sub in p.iterdir():
                    shutil.copy2(sub, dest / sub.name)
            else:
                shutil.copy2(p, dest)


def _extract_zip_to_dir(zip_path: Path, dest_dir: Path) -> None:
    """Extract zip into dest_dir (strip one top-level dir if single)."""
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    if not names:
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    top_dirs = {n.split("/")[0].split("\\")[0] for n in names if n}
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    if len(top_dirs) == 1 and names:
        single_top = list(top_dirs)[0]
        top_path = dest_dir / single_top
        if top_path.is_dir():
            for p in top_path.iterdir():
                shutil.move(str(p), str(dest_dir / p.name))
            top_path.rmdir()


def import_skills(sources: list[str | Path]) -> Path:
    """Import skills from GitHub tree URLs or zip URLs/paths into ~/.config/coala/skills.

    Each source is placed in its own subfolder (e.g. skills/bedtools/, skills/agent-skills/).

    - GitHub tree URL: downloads repo archive, copies folder into skills/<repo>/.
    - Zip URL or local zip: extracts into skills/<folder_name>/ (folder from URL path or zip stem).
    - Local directory: copies into skills/<dir_name>/.

    Returns the skills directory path.
    """
    skills_dir = SKILLS_DIR
    skills_dir.mkdir(parents=True, exist_ok=True)

    for src in sources:
        src_str = str(src).strip()
        if _is_url(src_str):
            parsed = _parse_github_tree_url(src_str)
            if parsed:
                owner, repo, branch, folder = parsed
                dest_dir = skills_dir / repo
                _download_github_folder(owner, repo, branch, folder, dest_dir)
            else:
                folder_name = _folder_name_for_source(src_str)
                dest_dir = skills_dir / folder_name
                with urlopen(src_str) as resp:
                    data = resp.read()
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
                    f.write(data)
                    f.flush()
                    try:
                        _extract_zip_to_dir(Path(f.name), dest_dir)
                    finally:
                        Path(f.name).unlink(missing_ok=True)
        else:
            path = Path(src).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Source not found: {path}")
            folder_name = _folder_name_for_source(path)
            dest_dir = skills_dir / folder_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            if path.suffix.lower() == ".zip":
                _extract_zip_to_dir(path, dest_dir)
            elif path.is_dir():
                for p in path.iterdir():
                    shutil.copy2(p, dest_dir / p.name)
            else:
                raise ValueError(f"Expected a zip file or directory: {path}")

    return skills_dir
