"""Docker cleanup (opt-in; requires Docker CLI)."""
from __future__ import annotations

import shutil
import subprocess
from typing import Iterable, List

from ..core.logger import get_logger
from .base import Category, CleanItem, Risk

_log = get_logger()


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _docker_disk_usage_bytes() -> int:
    """Return an estimate of reclaimable Docker space (bytes)."""
    try:
        out = subprocess.check_output(
            ["docker", "system", "df", "--format", "{{.Reclaimable}}"],
            text=True,
            timeout=15,
            creationflags=_no_window_flag(),
        )
    except Exception as exc:
        _log.debug("docker system df failed: %s", exc)
        return 0

    total = 0
    for raw in out.strip().splitlines():
        value = raw.split(" ", 1)[0].strip() if raw else ""
        if not value:
            continue
        total += _parse_docker_size(value)
    return total


def _parse_docker_size(value: str) -> int:
    value = value.strip()
    if not value:
        return 0
    units = {
        "B": 1,
        "KB": 10 ** 3,
        "MB": 10 ** 6,
        "GB": 10 ** 9,
        "TB": 10 ** 12,
        "K": 10 ** 3,
        "M": 10 ** 6,
        "G": 10 ** 9,
    }
    for suffix, multiplier in sorted(units.items(), key=lambda kv: -len(kv[0])):
        if value.upper().endswith(suffix):
            try:
                number = float(value[: -len(suffix)])
                return int(number * multiplier)
            except ValueError:
                return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def _no_window_flag() -> int:
    try:
        import subprocess as _sp

        return _sp.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    except Exception:
        return 0


def _docker_prune_all() -> None:
    subprocess.run(
        ["docker", "system", "prune", "-a", "-f", "--volumes"],
        check=False,
        timeout=900,
        creationflags=_no_window_flag(),
    )


def _docker_prune_builder() -> None:
    subprocess.run(
        ["docker", "builder", "prune", "-a", "-f"],
        check=False,
        timeout=600,
        creationflags=_no_window_flag(),
    )


class DockerCategory(Category):
    id = "docker"
    name = "Docker"
    description = (
        "Prune unused Docker images, containers, networks, volumes and build cache. "
        "Requires Docker CLI to be available in PATH."
    )

    def build_items(self) -> Iterable[CleanItem]:
        if not _docker_available():
            return []

        reclaimable = _docker_disk_usage_bytes()

        items: List[CleanItem] = []
        prune_all = CleanItem(
            id="docker.system_prune",
            name="docker system prune -a --volumes",
            paths=[],
            risk=Risk.MEDIUM,
            affects=(
                "Removes stopped containers, unused networks, dangling + unreferenced "
                "images and unused volumes. Running containers are untouched."
            ),
            reversible=False,
            default_selected=False,
            command=_docker_prune_all,
        )
        prune_all.size_bytes = reclaimable
        prune_all.detected = True
        items.append(prune_all)

        prune_builder = CleanItem(
            id="docker.builder_prune",
            name="docker builder prune -a",
            paths=[],
            risk=Risk.LOW,
            affects="Removes cached build layers from BuildKit.",
            reversible=False,
            default_selected=False,
            command=_docker_prune_builder,
        )
        prune_builder.detected = True
        items.append(prune_builder)

        return items
