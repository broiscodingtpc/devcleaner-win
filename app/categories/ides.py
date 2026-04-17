"""IDE cache cleanup (VS Code, Cursor, JetBrains)."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable, List

from ..core.safety import register_allowed_prefix
from .base import Category, CleanItem, Risk


VSCODE_FAMILIES = {
    "VS Code": "Code",
    "VS Code - Insiders": "Code - Insiders",
    "Cursor": "Cursor",
    "Windsurf": "Windsurf",
    "VSCodium": "VSCodium",
}


WORKSPACE_STORAGE_STALE_DAYS = 60


class IDEsCategory(Category):
    id = "ides"
    name = "IDE caches"
    description = (
        "Cached extension data, logs and stale workspace storage for VS Code, Cursor "
        "and JetBrains IDEs. Preferences, keybindings and installed extensions stay."
    )

    def build_items(self) -> Iterable[CleanItem]:
        items: List[CleanItem] = []

        roaming = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        home = Path.home()

        for label, folder in VSCODE_FAMILIES.items():
            root = roaming / folder
            if not root.exists():
                continue
            register_allowed_prefix(root)
            cache_paths = [
                root / "Cache",
                root / "CachedData",
                root / "CachedExtensions",
                root / "Code Cache",
                root / "GPUCache",
                root / "logs",
                root / "CachedProfilesData",
                root / "Service Worker" / "CacheStorage",
                root / "Service Worker" / "ScriptCache",
                root / "ShaderCache",
            ]
            items.append(
                CleanItem(
                    id=f"ide.{folder.lower().replace(' ', '-')}.cache",
                    name=f"{label} caches & logs",
                    paths=cache_paths,
                    risk=Risk.SAFE,
                    affects="Electron caches and logs for the editor. Rebuilt on next run.",
                    reversible=True,
                )
            )

            ws_storage = root / "User" / "workspaceStorage"
            if ws_storage.exists():
                stale = _stale_workspace_entries(ws_storage, WORKSPACE_STORAGE_STALE_DAYS)
                if stale:
                    items.append(
                        CleanItem(
                            id=f"ide.{folder.lower().replace(' ', '-')}.workspace_stale",
                            name=f"{label} stale workspaceStorage ({len(stale)} entries > {WORKSPACE_STORAGE_STALE_DAYS}d)",
                            paths=stale,
                            risk=Risk.MEDIUM,
                            affects=(
                                "Per-workspace history, chat, debugger state. Older than "
                                f"{WORKSPACE_STORAGE_STALE_DAYS} days. Next time you open "
                                "those projects the editor will start fresh."
                            ),
                            reversible=True,
                            default_selected=False,
                        )
                    )

        jetbrains = home / "AppData" / "Local" / "JetBrains"
        if jetbrains.exists():
            register_allowed_prefix(jetbrains)
            targets: List[Path] = []
            for product_dir in jetbrains.iterdir():
                if product_dir.is_dir():
                    for sub in ("caches", "log", "tmp"):
                        p = product_dir / sub
                        if p.exists():
                            targets.append(p)
            if targets:
                items.append(
                    CleanItem(
                        id="ide.jetbrains.caches",
                        name="JetBrains caches / logs / tmp",
                        paths=targets,
                        risk=Risk.LOW,
                        affects=(
                            "Indexing caches and logs for JetBrains IDEs. Re-indexing "
                            "happens on next project open (first open will be slower)."
                        ),
                        reversible=True,
                    )
                )

        vs_roaming = home / "AppData" / "Local" / "Microsoft" / "VisualStudio"
        if vs_roaming.exists():
            register_allowed_prefix(vs_roaming)
            caches: List[Path] = []
            try:
                for version in vs_roaming.iterdir():
                    if version.is_dir():
                        cache_candidates = [
                            version / "ComponentModelCache",
                            version / "TempPE",
                            version / "Cache",
                        ]
                        caches.extend([c for c in cache_candidates if c.exists()])
            except OSError:
                pass
            if caches:
                items.append(
                    CleanItem(
                        id="ide.visualstudio.caches",
                        name="Visual Studio component caches",
                        paths=caches,
                        risk=Risk.LOW,
                        affects="Visual Studio rebuilds these on next launch.",
                        reversible=True,
                    )
                )

        return [it for it in items if any(p.exists() for p in it.paths)]


def _stale_workspace_entries(storage: Path, days: int) -> List[Path]:
    cutoff = time.time() - days * 86400
    stale: List[Path] = []
    try:
        for entry in storage.iterdir():
            if not entry.is_dir():
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                stale.append(entry)
    except OSError:
        pass
    return stale
