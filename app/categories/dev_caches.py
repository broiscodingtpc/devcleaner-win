"""Package manager caches (not project build output)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

from ..core.safety import register_allowed_prefix
from .base import Category, CleanItem, Risk


class DevCachesCategory(Category):
    id = "dev_caches"
    name = "Dev package caches"
    description = (
        "Downloaded archives stored by npm / yarn / pnpm / pip / poetry / cargo / go / "
        "maven / gradle. Caches rebuild automatically on next install."
    )

    def build_items(self) -> Iterable[CleanItem]:
        home = Path.home()
        local = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
        roaming = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))

        items: List[CleanItem] = []

        def add(
            iid: str,
            name: str,
            path: Path,
            affects: str,
            *,
            risk: Risk = Risk.LOW,
            default_selected: bool = True,
        ) -> None:
            register_allowed_prefix(path)
            items.append(
                CleanItem(
                    id=iid,
                    name=name,
                    paths=[path],
                    risk=risk,
                    affects=affects,
                    reversible=False,
                    recreated_automatically=True,
                    default_selected=default_selected,
                )
            )

        add(
            "dev.npm_cache",
            "npm cache",
            roaming / "npm-cache",
            "npm redownloads packages on next install.",
        )
        add(
            "dev.npm_cache_local",
            "npm cache (LOCALAPPDATA)",
            local / "npm-cache",
            "npm redownloads packages on next install.",
        )
        add(
            "dev.pnpm_store",
            "pnpm store",
            local / "pnpm" / "store",
            "pnpm content-addressable store. pnpm redownloads on next install.",
        )
        add(
            "dev.pnpm_store_home",
            "pnpm store (home)",
            home / ".pnpm-store",
            "pnpm content-addressable store. pnpm redownloads on next install.",
        )
        add(
            "dev.yarn_cache",
            "Yarn v1 cache",
            local / "Yarn" / "Cache",
            "Yarn classic cache.",
        )
        add(
            "dev.yarn_berry_global",
            "Yarn berry global cache",
            home / ".yarn" / "berry" / "cache",
            "Yarn 2+ global cache.",
        )
        add(
            "dev.pip_cache",
            "pip cache",
            local / "pip" / "Cache",
            "pip redownloads wheels on next install.",
        )
        add(
            "dev.pip_cache_home",
            "pip cache (home)",
            home / ".cache" / "pip",
            "pip redownloads wheels on next install.",
        )
        add(
            "dev.poetry_cache",
            "Poetry cache",
            local / "pypoetry" / "Cache",
            "Poetry redownloads packages on next install.",
        )
        add(
            "dev.pipenv_cache",
            "Pipenv cache",
            local / "pipenv" / "Cache",
            "Pipenv rebuilds the cache on next install.",
        )
        add(
            "dev.conda_pkgs",
            "Conda pkgs cache",
            home / ".conda" / "pkgs",
            "Conda will redownload packages on next env creation.",
            default_selected=False,
        )
        add(
            "dev.cargo_registry",
            "Cargo registry cache",
            home / ".cargo" / "registry" / "cache",
            "Cargo redownloads crates on next build.",
        )
        add(
            "dev.cargo_registry_src",
            "Cargo registry src",
            home / ".cargo" / "registry" / "src",
            "Extracted crate sources. Cargo re-extracts on demand.",
            default_selected=False,
        )
        add(
            "dev.gradle_caches",
            "Gradle caches",
            home / ".gradle" / "caches",
            "Gradle redownloads dependencies on next build.",
            default_selected=False,
        )
        add(
            "dev.maven_repository",
            "Maven local repository",
            home / ".m2" / "repository",
            "Maven redownloads artifacts on next build. May be several GB.",
            default_selected=False,
        )
        add(
            "dev.go_mod_cache",
            "Go module cache",
            home / "go" / "pkg" / "mod",
            "Go redownloads modules on next build. Read-only files take extra time.",
            default_selected=False,
        )
        add(
            "dev.nuget_cache",
            "NuGet global packages",
            home / ".nuget" / "packages",
            ".NET redownloads packages on next build.",
            default_selected=False,
        )
        add(
            "dev.rustup_tmp",
            "rustup temporary downloads",
            home / ".rustup" / "tmp",
            "Temporary rustup installer downloads.",
        )
        add(
            "dev.flutter_pub",
            "Flutter pub cache",
            local / "Pub" / "Cache",
            "Dart / Flutter redownloads packages on next build.",
            default_selected=False,
        )

        return [it for it in items if any(p.exists() for p in it.paths)]
