"""Recursive scan for Python build/test artifacts across the user's source trees."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Tuple

from ..core.logger import get_logger
from ..core.settings import load_settings
from .base import Category, CleanItem, Risk

_log = get_logger()

ARTIFACT_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".hypothesis",
    ".coverage",
}

SCAN_EXCLUDES = {
    "node_modules",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    "out",
    ".next",
    ".turbo",
    "target",
    ".cache",
    ".local",
    ".pnpm-store",
    ".yarn",
    "AppData",
    "Library",
    "OneDrive",
    "Dropbox",
}


def _default_scan_roots() -> List[Path]:
    """Return the default roots we walk for Python artifacts.

    We bias toward common developer folders to keep the scan fast.
    """
    home = Path.home()
    candidates = [
        home / "source",
        home / "Source",
        home / "src",
        home / "Dev",
        home / "dev",
        home / "Projects",
        home / "projects",
        home / "Code",
        home / "code",
        home / "Work",
        home / "work",
        home / "Desktop",
        home / "Documents" / "GitHub",
        home / "Documents" / "Projects",
        home / "Repos",
        home / "repos",
        home / "git",
        home / "GitHub",
    ]
    seen = set()
    out: List[Path] = []
    for c in candidates:
        if c.exists() and c.is_dir():
            key = str(c.resolve())
            if key not in seen:
                seen.add(key)
                out.append(c)
    return out


def _scan_for_artifacts(roots: Iterable[Path], *, max_depth: int = 10) -> List[Tuple[Path, str]]:
    found: List[Tuple[Path, str]] = []
    for root in roots:
        if not root.exists():
            continue
        base_depth = len(root.parts)
        try:
            for dirpath, dirnames, _filenames in os.walk(root):
                depth = len(Path(dirpath).parts) - base_depth
                if depth > max_depth:
                    dirnames[:] = []
                    continue
                pruned = []
                keep = []
                for d in dirnames:
                    if d in ARTIFACT_NAMES:
                        found.append((Path(dirpath) / d, d))
                        pruned.append(d)
                    elif d in SCAN_EXCLUDES or d.startswith(".venv"):
                        pruned.append(d)
                    else:
                        keep.append(d)
                dirnames[:] = keep
        except (PermissionError, OSError) as exc:
            _log.debug("skip %s: %s", root, exc)
    return found


class PythonArtifactsCategory(Category):
    id = "python_artifacts"
    name = "Python project artifacts"
    description = (
        "__pycache__, .pytest_cache, .mypy_cache, .ruff_cache and similar folders found "
        "recursively inside your project directories."
    )

    def build_items(self) -> Iterable[CleanItem]:
        settings = load_settings()
        roots = _default_scan_roots()
        extra = [Path(p).expanduser() for p in settings.extra_scan_roots if p]
        all_roots = roots + [p for p in extra if p.exists() and p.is_dir()]

        if not all_roots:
            return []

        hits = _scan_for_artifacts(all_roots)
        if not hits:
            return []

        by_kind: dict[str, List[Path]] = {}
        for path, kind in hits:
            by_kind.setdefault(kind, []).append(path)

        descriptions = {
            "__pycache__": (
                "Compiled bytecode. Recreated automatically at next Python import."
            ),
            ".pytest_cache": "pytest cache. Recreated on next pytest run.",
            ".mypy_cache": "mypy incremental cache. Recreated on next mypy run.",
            ".ruff_cache": "Ruff incremental cache. Recreated on next lint.",
            ".tox": "tox virtualenvs. Recreated on next `tox` invocation.",
            ".nox": "nox virtualenvs. Recreated on next `nox` invocation.",
            ".hypothesis": "Hypothesis example database.",
            ".coverage": "coverage.py data files.",
        }

        items: List[CleanItem] = []
        for kind, paths in by_kind.items():
            items.append(
                CleanItem(
                    id=f"py.{kind.strip('.').replace('_', '-')}",
                    name=f"{kind} folders ({len(paths)} found)",
                    paths=sorted(paths),
                    risk=Risk.SAFE,
                    affects=descriptions.get(kind, "Python development artifact."),
                    reversible=True,
                    needs_extra_allowed=list({p.parent for p in paths}),
                )
            )
        return items
