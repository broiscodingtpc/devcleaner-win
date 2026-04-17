"""GPU shader caches and game launcher caches."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

from ..core.safety import register_allowed_prefix
from .base import Category, CleanItem, Risk


class GamingCategory(Category):
    id = "gaming"
    name = "GPU & gaming caches"
    description = (
        "Shader caches produced by NVIDIA, AMD, DirectX and Steam. Games rebuild the "
        "cache on first launch (loading may be slightly slower the first time)."
    )

    def build_items(self) -> Iterable[CleanItem]:
        home = Path.home()
        local = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
        programdata = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))

        items: List[CleanItem] = []

        def add(
            iid: str,
            name: str,
            paths: List[Path],
            affects: str,
            *,
            default_selected: bool = True,
            risk: Risk = Risk.LOW,
        ) -> None:
            for p in paths:
                register_allowed_prefix(p)
            items.append(
                CleanItem(
                    id=iid,
                    name=name,
                    paths=paths,
                    risk=risk,
                    affects=affects,
                    reversible=False,
                    default_selected=default_selected,
                )
            )

        add(
            "gaming.nvidia_dx",
            "NVIDIA DirectX shader cache",
            [
                local / "NVIDIA" / "DXCache",
                local / "NVIDIA" / "GLCache",
                local / "NVIDIA" / "ComputeCache",
            ],
            "NVIDIA GPU driver shader cache. Rebuilt by the driver on demand.",
        )
        add(
            "gaming.amd_shader",
            "AMD shader cache",
            [
                local / "AMD" / "DxCache",
                local / "AMD" / "GLCache",
                local / "AMD" / "VkCache",
            ],
            "AMD GPU driver shader cache. Rebuilt on demand.",
        )
        add(
            "gaming.directx_shader",
            "DirectX shader cache",
            [
                local / "D3DSCache",
            ],
            "Windows DirectX shader cache.",
        )
        add(
            "gaming.steam_shader",
            "Steam shader cache",
            [
                programdata / "Steam" / "shadercache",
                Path(r"C:\Program Files (x86)") / "Steam" / "steamapps" / "shadercache",
            ],
            "Steam-managed shader caches. Rebuilt by each game on next launch.",
            default_selected=False,
        )
        add(
            "gaming.epic_webcache",
            "Epic Games launcher webcache",
            [
                local / "EpicGamesLauncher" / "Saved" / "webcache",
                local / "EpicGamesLauncher" / "Saved" / "webcache_4147",
                local / "EpicGamesLauncher" / "Saved" / "Logs",
            ],
            "Epic launcher web UI cache and logs.",
        )

        return [it for it in items if any(p.exists() for p in it.paths)]
