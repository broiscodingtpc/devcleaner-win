"""Windows-specific path helpers for safe deletion."""
from __future__ import annotations

import os
from pathlib import Path


def extended_length_str(path: Path | str) -> str:
    """Return a path string usable with Win32 APIs when MAX_PATH would be exceeded.

    Prefixes with ``\\\\?\\`` (or ``\\\\?\\UNC\\`` for UNC paths). No-op on non-Windows.
    """
    if os.name != "nt":
        return os.path.abspath(str(path))

    p = Path(path).resolve()
    s = os.path.normpath(str(p))
    if s.startswith("\\\\?\\"):
        return s
    if s.startswith("\\\\"):
        return "\\\\?\\UNC\\" + s[2:]
    return "\\\\?\\" + s


def format_os_error(exc: OSError) -> str:
    """Human-readable hint for common Windows delete failures."""
    errno = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
    if errno == 5 or errno == 13:
        return f"{exc} (access denied — close apps using these files or run as Administrator)"
    if errno == 32:
        return f"{exc} (file in use by another process)"
    if errno == 145:
        return f"{exc} (directory not empty — will retry or skip)"
    return str(exc)
