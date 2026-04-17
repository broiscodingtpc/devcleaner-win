"""Cleanup categories registry."""
from __future__ import annotations

from typing import List

from .base import Category
from .windows_system import WindowsSystemCategory
from .browsers import BrowsersCategory
from .dev_caches import DevCachesCategory
from .ai_caches import AICachesCategory
from .python_artifacts import PythonArtifactsCategory
from .node_modules import NodeModulesCategory
from .ides import IDEsCategory
from .gaming import GamingCategory
from .docker import DockerCategory


def all_categories() -> List[Category]:
    """Return one instance of every category in display order."""
    return [
        WindowsSystemCategory(),
        BrowsersCategory(),
        DevCachesCategory(),
        AICachesCategory(),
        PythonArtifactsCategory(),
        NodeModulesCategory(),
        IDEsCategory(),
        GamingCategory(),
        DockerCategory(),
    ]


__all__ = ["Category", "all_categories"]
