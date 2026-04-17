"""Windows system cleanup targets."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

from ..core.safety import register_allowed_prefix
from .base import Category, CleanItem, Risk


def _env_path(name: str, *extra: str) -> Path | None:
    root = os.environ.get(name)
    if not root:
        return None
    return Path(root, *extra)


class WindowsSystemCategory(Category):
    id = "windows_system"
    name = "Windows System"
    description = "Temporary files, caches and log folders produced by Windows itself."

    def build_items(self) -> Iterable[CleanItem]:
        items: List[CleanItem] = []

        user_temp = _env_path("TEMP") or _env_path("TMP")
        win_temp = _env_path("WINDIR", "Temp")
        local = _env_path("LOCALAPPDATA")
        windir = _env_path("WINDIR") or Path(r"C:\Windows")
        system_drive = Path(os.environ.get("SYSTEMDRIVE", "C:") + "\\")

        if user_temp:
            register_allowed_prefix(user_temp)
            items.append(
                CleanItem(
                    id="win.user_temp",
                    name="User temp folder",
                    paths=[user_temp],
                    risk=Risk.SAFE,
                    affects=(
                        "Installer leftovers, extracted archives, editor autosaves older "
                        "than the current session. Recreated on demand."
                    ),
                    reversible=True,
                    requires_admin=False,
                )
            )

        if win_temp:
            register_allowed_prefix(win_temp)
            items.append(
                CleanItem(
                    id="win.system_temp",
                    name="System temp folder (C:\\Windows\\Temp)",
                    paths=[win_temp],
                    risk=Risk.SAFE,
                    affects="System-wide scratch space. Safe to empty when idle.",
                    reversible=True,
                    requires_admin=True,
                )
            )

        if windir:
            prefetch = windir / "Prefetch"
            register_allowed_prefix(prefetch)
            items.append(
                CleanItem(
                    id="win.prefetch",
                    name="Windows Prefetch",
                    paths=[prefetch],
                    risk=Risk.LOW,
                    affects=(
                        "Boot / app launch hints. Windows rebuilds them; first few "
                        "launches of popular apps may feel slightly slower."
                    ),
                    reversible=False,
                    requires_admin=True,
                    default_selected=False,
                )
            )

            wu_download = windir / "SoftwareDistribution" / "Download"
            register_allowed_prefix(wu_download)
            items.append(
                CleanItem(
                    id="win.wu_cache",
                    name="Windows Update download cache",
                    paths=[wu_download],
                    risk=Risk.SAFE,
                    affects=(
                        "Downloaded update payloads. Safe once updates are installed; "
                        "pending updates will be re-downloaded."
                    ),
                    reversible=False,
                    requires_admin=True,
                )
            )

            delivery_opt = windir / "SoftwareDistribution" / "DeliveryOptimization"
            register_allowed_prefix(delivery_opt)
            items.append(
                CleanItem(
                    id="win.delivery_optimization",
                    name="Delivery Optimization cache",
                    paths=[delivery_opt],
                    risk=Risk.SAFE,
                    affects="Peer-to-peer update cache. Windows rebuilds as needed.",
                    reversible=False,
                    requires_admin=True,
                    default_selected=False,
                )
            )

            logs = windir / "Logs"
            register_allowed_prefix(logs)
            items.append(
                CleanItem(
                    id="win.windows_logs",
                    name="Windows component logs (C:\\Windows\\Logs)",
                    paths=[logs / "CBS", logs / "DPX", logs / "WindowsUpdate"],
                    risk=Risk.LOW,
                    affects="Component servicing and update logs.",
                    reversible=False,
                    requires_admin=True,
                    default_selected=False,
                )
            )

        if local:
            crash_dumps = local / "CrashDumps"
            register_allowed_prefix(crash_dumps)
            items.append(
                CleanItem(
                    id="win.crash_dumps",
                    name="Application crash dumps",
                    paths=[crash_dumps],
                    risk=Risk.SAFE,
                    affects="Post-mortem dumps of crashed applications.",
                    reversible=True,
                )
            )

            wer = local / "Microsoft" / "Windows" / "WER"
            register_allowed_prefix(wer)
            items.append(
                CleanItem(
                    id="win.error_reports",
                    name="Windows Error Reporting",
                    paths=[wer / "ReportArchive", wer / "ReportQueue", wer / "Temp"],
                    risk=Risk.SAFE,
                    affects="Queued crash reports that were not sent to Microsoft.",
                    reversible=True,
                )
            )

            inetcache = local / "Microsoft" / "Windows" / "INetCache"
            register_allowed_prefix(inetcache)
            items.append(
                CleanItem(
                    id="win.ie_cache",
                    name="Internet Explorer / legacy IE cache",
                    paths=[inetcache],
                    risk=Risk.SAFE,
                    affects="Used by legacy WebView controls in some apps.",
                    reversible=True,
                    default_selected=False,
                )
            )

            explorer_cache = local / "Microsoft" / "Windows" / "Explorer"
            register_allowed_prefix(explorer_cache)
            thumb_files = [
                explorer_cache / fname
                for fname in (
                    "thumbcache_32.db",
                    "thumbcache_96.db",
                    "thumbcache_256.db",
                    "thumbcache_1024.db",
                    "thumbcache_idx.db",
                    "thumbcache_sr.db",
                    "iconcache_32.db",
                    "iconcache_48.db",
                    "iconcache_96.db",
                    "iconcache_256.db",
                )
            ]
            items.append(
                CleanItem(
                    id="win.thumb_icon_cache",
                    name="Thumbnail & icon cache",
                    paths=thumb_files,
                    risk=Risk.SAFE,
                    affects=(
                        "Explorer rebuilds thumbnails/icons on next browse. First browse "
                        "of a folder with many images may flicker briefly."
                    ),
                    reversible=True,
                    default_selected=False,
                )
            )

        recycle = system_drive / "$Recycle.Bin"
        register_allowed_prefix(recycle)
        items.append(
            CleanItem(
                id="win.recycle_bin",
                name="Empty Recycle Bin",
                paths=[recycle],
                risk=Risk.MEDIUM,
                affects=(
                    "All files currently in the Recycle Bin will be permanently erased. "
                    "Review before confirming."
                ),
                reversible=False,
                requires_admin=True,
                default_selected=False,
            )
        )

        windows_old = system_drive / "Windows.old"
        if windows_old.exists():
            register_allowed_prefix(windows_old)
            items.append(
                CleanItem(
                    id="win.windows_old",
                    name="Windows.old (previous OS install)",
                    paths=[windows_old],
                    risk=Risk.HIGH,
                    affects=(
                        "Folder left after a Windows upgrade. Typically 10-30 GB. "
                        "Removes the ability to roll back to the previous Windows version."
                    ),
                    reversible=False,
                    requires_admin=True,
                    default_selected=False,
                )
            )

        return items
