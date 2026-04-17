"""Detect localhost listeners and highlight likely-forgotten dev servers."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import psutil

from ..core.logger import get_logger

_log = get_logger()


DEV_PORTS = {
    3000, 3001, 3002, 3030, 3333,
    4000, 4200, 4321,
    5000, 5001, 5173, 5174, 5500,
    6006,
    7000, 7860,
    8000, 8001, 8008, 8080, 8081, 8088, 8888,
    9000, 9090, 9229,
}

SYSTEM_PROCESS_NAMES = {
    "svchost.exe", "services.exe", "system", "idle", "lsass.exe",
    "winlogon.exe", "csrss.exe", "wininit.exe", "spoolsv.exe",
    "dnscache", "rpcss", "mdnsresponder.exe",
}

TERMINAL_PARENT_NAMES = {
    "cmd.exe", "powershell.exe", "pwsh.exe", "wt.exe",
    "bash.exe", "zsh.exe", "fish.exe", "sh.exe", "conhost.exe",
    "windowsterminal.exe",
}


@dataclass
class PortEntry:
    port: int
    address: str
    pid: int
    name: str
    exe: str
    cmdline: str
    cwd: str
    username: str
    parent_pid: int
    parent_name: str
    uptime_seconds: float
    is_system: bool
    likely_forgotten: bool
    forgotten_reason: str = ""


def _safe(fn, default=""):
    try:
        return fn()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return default


def _is_localhost(address: str) -> bool:
    return address in ("127.0.0.1", "::1", "0.0.0.0", "::")


def list_listening_ports() -> List[PortEntry]:
    """Return a list of TCP LISTEN sockets bound to local interfaces."""
    entries: List[PortEntry] = []
    now = time.time()

    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError) as exc:
        _log.warning("net_connections denied: %s - try running as admin", exc)
        connections = []
    except Exception as exc:
        _log.error("net_connections failed: %s", exc)
        connections = []

    seen: set[tuple[int, int]] = set()

    for conn in connections:
        if conn.status != psutil.CONN_LISTEN:
            continue
        if conn.type != 1:  # SOCK_STREAM
            continue
        if not conn.laddr:
            continue
        address = conn.laddr.ip
        port = conn.laddr.port
        if not _is_localhost(address):
            continue

        pid = conn.pid or 0
        key = (pid, port)
        if key in seen:
            continue
        seen.add(key)

        try:
            proc = psutil.Process(pid) if pid else None
        except psutil.NoSuchProcess:
            proc = None

        if proc is None:
            entries.append(
                PortEntry(
                    port=port,
                    address=address,
                    pid=pid,
                    name="?",
                    exe="",
                    cmdline="",
                    cwd="",
                    username="",
                    parent_pid=0,
                    parent_name="",
                    uptime_seconds=0.0,
                    is_system=True,
                    likely_forgotten=False,
                    forgotten_reason="unknown process",
                )
            )
            continue

        name = _safe(lambda: proc.name(), "?") or "?"
        exe = _safe(lambda: proc.exe() or "", "")
        cmdline_parts = _safe(lambda: proc.cmdline() or [], [])
        cmdline = " ".join(str(p) for p in cmdline_parts)
        cwd = _safe(lambda: proc.cwd() or "", "")
        username = _safe(lambda: proc.username() or "", "")
        create_time = _safe(lambda: proc.create_time() or now, now)
        uptime = max(0.0, now - create_time)

        parent = _safe(lambda: proc.parent(), None)
        parent_pid = 0
        parent_name = ""
        parent_alive = False
        if parent is not None:
            parent_pid = parent.pid
            parent_name = _safe(lambda: parent.name() or "", "")
            parent_alive = _safe(lambda: parent.is_running(), False)

        is_system = (
            name.lower() in SYSTEM_PROCESS_NAMES
            or (exe and exe.lower().startswith(os.environ.get("WINDIR", r"C:\Windows").lower()))
            or username.endswith("SYSTEM")
            or username.endswith("LOCAL SERVICE")
            or username.endswith("NETWORK SERVICE")
        )

        forgotten = False
        forgotten_reason = ""
        if not is_system:
            if port in DEV_PORTS and uptime > 3600:
                forgotten = True
                forgotten_reason = "dev port, uptime > 1h"
            if parent_name.lower() in TERMINAL_PARENT_NAMES and not parent_alive:
                forgotten = True
                forgotten_reason = "terminal parent closed"
            if parent_pid == 0 and uptime > 3600 and port in DEV_PORTS:
                forgotten = True
                forgotten_reason = "orphaned dev server"

        entries.append(
            PortEntry(
                port=port,
                address=address,
                pid=pid,
                name=name,
                exe=exe,
                cmdline=cmdline,
                cwd=cwd,
                username=username,
                parent_pid=parent_pid,
                parent_name=parent_name,
                uptime_seconds=uptime,
                is_system=is_system,
                likely_forgotten=forgotten,
                forgotten_reason=forgotten_reason,
            )
        )

    entries.sort(key=lambda e: (not e.likely_forgotten, e.is_system, e.port))
    return entries


def kill_process(pid: int, *, force: bool = False, timeout: float = 3.0) -> tuple[bool, str]:
    """Terminate a process by PID. Returns (success, message)."""
    if pid <= 0:
        return False, "invalid pid"
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return True, "already gone"

    name = _safe(lambda: proc.name(), f"pid {pid}")
    try:
        if force:
            proc.kill()
        else:
            proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except psutil.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=timeout)
        _log.info("killed process %s (pid %d)", name, pid)
        return True, f"killed {name}"
    except psutil.AccessDenied as exc:
        _log.warning("access denied killing %s (pid %d): %s", name, pid, exc)
        return False, "access denied - run as admin"
    except Exception as exc:
        _log.error("failed to kill %s (pid %d): %s", name, pid, exc)
        return False, str(exc)


def format_uptime(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    if hours < 24:
        return f"{hours}h {minutes}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"
