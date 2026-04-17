"""Safety guard for every destructive operation.

The executor must never touch a path unless it passes through
:func:`assert_safe_to_delete`. We use two layers:

1. An explicit *allow-list* of directory prefixes known to be disposable
   (temp folders, package caches, browser caches, ...).
2. An explicit *deny-list* that overrides the allow-list for paths the user
   almost certainly does not want removed (Documents, Desktop, Pictures,
   System32, Program Files, ...).

The allow-list is intentionally conservative - categories may register new
prefixes at import time via :func:`register_allowed_prefix`.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Iterable, Set


class UnsafePathError(Exception):
    """Raised when a cleanup target is not on the allow-list."""


_ALLOWED_PREFIXES: Set[Path] = set()
_DENIED_PREFIXES: Set[Path] = set()
_lock = threading.Lock()


def _norm(p: Path | str) -> Path:
    try:
        return Path(p).expanduser().resolve(strict=False)
    except Exception:
        return Path(str(p))


def register_allowed_prefix(path: Path | str) -> None:
    normalized = _norm(path)
    with _lock:
        _ALLOWED_PREFIXES.add(normalized)


def register_denied_prefix(path: Path | str) -> None:
    normalized = _norm(path)
    with _lock:
        _DENIED_PREFIXES.add(normalized)


def allowed_prefixes() -> Iterable[Path]:
    with _lock:
        return tuple(_ALLOWED_PREFIXES)


def denied_prefixes() -> Iterable[Path]:
    with _lock:
        return tuple(_DENIED_PREFIXES)


def _bootstrap_defaults() -> None:
    """Register default Windows-friendly allow / deny roots."""
    if os.name == "nt":
        temp = os.environ.get("TEMP") or os.environ.get("TMP")
        if temp:
            register_allowed_prefix(temp)
        windir = os.environ.get("WINDIR") or r"C:\Windows"
        register_allowed_prefix(Path(windir) / "Temp")
        register_allowed_prefix(Path(windir) / "SoftwareDistribution" / "Download")
        register_allowed_prefix(Path(windir) / "Prefetch")
        register_allowed_prefix(Path(windir) / "Logs")

        local = os.environ.get("LOCALAPPDATA")
        if local:
            register_allowed_prefix(Path(local) / "Temp")
            register_allowed_prefix(Path(local) / "CrashDumps")
            register_allowed_prefix(Path(local) / "Microsoft" / "Windows" / "INetCache")
            register_allowed_prefix(
                Path(local) / "Microsoft" / "Windows" / "Explorer"
            )
            register_allowed_prefix(
                Path(local) / "Microsoft" / "Windows" / "WER"
            )

        system_drive = os.environ.get("SYSTEMDRIVE", "C:")
        register_allowed_prefix(Path(system_drive) / "$Recycle.Bin")

        register_denied_prefix(Path(windir) / "System32")
        register_denied_prefix(Path(windir) / "SysWOW64")
        register_denied_prefix(r"C:\Program Files")
        register_denied_prefix(r"C:\Program Files (x86)")
        register_denied_prefix(r"C:\ProgramData\Microsoft\Windows")

    home = Path.home()
    for folder in ("Documents", "Desktop", "Pictures", "Videos", "Music"):
        register_denied_prefix(home / folder)
    register_denied_prefix(home / "OneDrive")


_bootstrap_defaults()


def is_under(target: Path, root: Path) -> bool:
    """Return True when *target* is equal to or inside *root*."""
    try:
        target = _norm(target)
        root = _norm(root)
    except Exception:
        return False
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


def assert_safe_to_delete(path: Path | str, *, extra_allowed: Iterable[Path | str] = ()) -> Path:
    """Raise :class:`UnsafePathError` if *path* is not cleanup-safe.

    Returns the normalized :class:`Path` when the check passes so callers can
    use the result as the canonical version.
    """
    p = _norm(path)
    if not p.drive and os.name == "nt":
        raise UnsafePathError(f"refusing path without drive: {path}")

    # Hard deny wins over allow.
    for deny in denied_prefixes():
        if p == deny or is_under(p, deny):
            # Allow a nested __pycache__/.pytest_cache/etc. inside denied roots only
            # when the caller explicitly adds it to extra_allowed.
            allowed_extra = any(is_under(p, _norm(e)) or p == _norm(e) for e in extra_allowed)
            if not allowed_extra:
                raise UnsafePathError(f"path is in a protected location: {p}")

    # Accept user-contributed extras first.
    for extra in extra_allowed:
        extra_p = _norm(extra)
        if p == extra_p or is_under(p, extra_p):
            return p

    for allowed in allowed_prefixes():
        if p == allowed or is_under(p, allowed):
            return p

    raise UnsafePathError(
        f"path is not on the cleanup allow-list: {p}. "
        "Add it to extra_allowed or register an allowed prefix."
    )
