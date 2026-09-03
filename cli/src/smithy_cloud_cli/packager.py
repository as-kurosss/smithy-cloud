"""Read a project directory into a JSON-serialisable files dict and requirements."""

from __future__ import annotations

import fnmatch
from pathlib import Path

_EXCLUDE_DIRS: set[str] = {".git", ".venv", "__pycache__", "node_modules"}
_EXCLUDE_GLOBS: set[str] = {"*.pyc", "*.pyo", ".env"}


def read_directory(path: str | Path) -> dict[str, str]:
    """Walk *path* recursively and return ``{relative_path: content}`` dicts.

    Skips directories and files in ``_EXCLUDE_DIRS`` / ``_EXCLUDE_GLOBS``.
    Binary files (those that raise :class:`UnicodeDecodeError`) are silently
    skipped.
    """
    root = Path(path).resolve()
    files: dict[str, str] = {}

    for entry in sorted(root.rglob("*")):
        if not entry.is_file():
            continue

        # Directory name check (walks through each parent too).
        if any(part in _EXCLUDE_DIRS for part in entry.relative_to(root).parts):
            continue

        name = entry.name
        if any(fnmatch.fnmatch(name, pat) for pat in _EXCLUDE_GLOBS):
            continue

        rel = entry.relative_to(root).as_posix()
        try:
            files[rel] = entry.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary file — skip

    return files


def read_requirements(path: str | Path | None = None) -> list[str]:
    """Return requirements lines from *requirements.txt* if it exists.

    Parameters
    ----------
    path:
        Directory that may contain ``requirements.txt``.  Defaults to cwd.
    """
    req_file = Path(path) if path else Path.cwd()
    req_file = req_file / "requirements.txt"

    if not req_file.is_file():
        return []

    lines = [
        line.strip()
        for line in req_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return lines
