"""Admin / UAC helpers.

The cleaner needs elevation for several categories (Windows Update cache,
SoftwareDistribution, Event Logs, Prefetch, ...). We detect admin status
and expose a helper to re-launch the current executable with UAC.
"""
from __future__ import annotations

import ctypes
import os
import sys
from typing import Sequence


def is_admin() -> bool:
    """Return True when the current process has administrative privileges."""
    if os.name != "nt":
        return os.geteuid() == 0  # type: ignore[attr-defined]
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(extra_args: Sequence[str] | None = None) -> bool:
    """Re-launch the current process with a UAC elevation prompt.

    Returns True if ShellExecuteW accepted the request. The caller should
    typically exit the current non-elevated instance right after.
    """
    if os.name != "nt":
        return False

    params = list(sys.argv[1:])
    if extra_args:
        params.extend(extra_args)

    if getattr(sys, "frozen", False):
        executable = sys.executable
        argument_string = " ".join(_quote(p) for p in params)
    else:
        executable = sys.executable
        script = os.path.abspath(sys.argv[0])
        argument_string = " ".join([_quote(script), *[_quote(p) for p in params]])

    try:
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, argument_string, None, 1
        )
        return rc > 32
    except Exception:
        return False


def _quote(value: str) -> str:
    if not value:
        return '""'
    if any(c.isspace() or c == '"' for c in value):
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value
