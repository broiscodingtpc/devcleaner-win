"""Browser cache cleanup - we deliberately skip history / cookies / passwords."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

from ..core.safety import register_allowed_prefix
from .base import Category, CleanItem, Risk


def _chromium_profiles(root: Path) -> List[Path]:
    """Return the list of profile directories inside a Chromium User Data folder."""
    profiles: List[Path] = []
    if not root.exists():
        return profiles
    try:
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            if name == "Default" or name.startswith("Profile "):
                profiles.append(entry)
    except OSError:
        pass
    return profiles


CHROMIUM_CACHE_SUBDIRS = [
    "Cache",
    "Code Cache",
    "GPUCache",
    "Service Worker/CacheStorage",
    "Service Worker/ScriptCache",
]


class BrowsersCategory(Category):
    id = "browsers"
    name = "Browser caches"
    description = (
        "Only disk caches are removed. Bookmarks, history, cookies, saved passwords "
        "and extensions stay intact."
    )

    def build_items(self) -> Iterable[CleanItem]:
        items: List[CleanItem] = []
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        roaming = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))

        chromium_targets = {
            "Chrome": local / "Google" / "Chrome" / "User Data",
            "Edge": local / "Microsoft" / "Edge" / "User Data",
            "Brave": local / "BraveSoftware" / "Brave-Browser" / "User Data",
            "Opera": roaming / "Opera Software" / "Opera Stable",
            "Vivaldi": local / "Vivaldi" / "User Data",
        }

        for label, root in chromium_targets.items():
            if not root.exists():
                continue
            register_allowed_prefix(root)
            profiles = _chromium_profiles(root) or [root]
            for profile in profiles:
                paths = [profile / sub for sub in CHROMIUM_CACHE_SUBDIRS]
                items.append(
                    CleanItem(
                        id=f"browser.{label.lower()}.{profile.name.lower().replace(' ', '_')}",
                        name=f"{label} - {profile.name} cache",
                        paths=paths,
                        risk=Risk.SAFE,
                        affects=(
                            f"{label} on-disk caches (page assets, GPU shaders, service "
                            "workers). Bookmarks, history, passwords and extensions stay. "
                            "First visit to each site will re-download assets."
                        ),
                        reversible=True,
                    )
                )

        firefox_root = roaming / "Mozilla" / "Firefox" / "Profiles"
        firefox_cache_root = local / "Mozilla" / "Firefox" / "Profiles"
        if firefox_root.exists() or firefox_cache_root.exists():
            register_allowed_prefix(firefox_root)
            register_allowed_prefix(firefox_cache_root)
            caches: List[Path] = []
            try:
                if firefox_cache_root.exists():
                    for profile in firefox_cache_root.iterdir():
                        if profile.is_dir():
                            caches.extend(
                                [
                                    profile / "cache2",
                                    profile / "startupCache",
                                    profile / "shader-cache",
                                    profile / "jumpListCache",
                                ]
                            )
            except OSError:
                pass
            if caches:
                items.append(
                    CleanItem(
                        id="browser.firefox.cache",
                        name="Firefox profile caches",
                        paths=caches,
                        risk=Risk.SAFE,
                        affects=(
                            "Firefox cache2 / startupCache / shader cache. History, "
                            "bookmarks, logins, add-ons stay intact."
                        ),
                        reversible=True,
                    )
                )

        return items
