"""Base classes for cleanup categories."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, List, Optional


class Risk(str, Enum):
    SAFE = "Safe"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


RISK_ORDER = {Risk.SAFE: 0, Risk.LOW: 1, Risk.MEDIUM: 2, Risk.HIGH: 3}


@dataclass
class CleanItem:
    """A single cleanable target shown in the UI.

    Attributes:
        id: Stable identifier, used to persist user selection overrides.
        name: Short title.
        paths: Filesystem paths to delete (directory or file).
        risk: See :class:`Risk`.
        affects: Plain-language explanation shown in the detail panel.
        recreated_automatically: Whether the target will regenerate on normal use.
        reversible: Whether the delete can be undone (Recycle Bin, etc.).
        default_selected: Initial checkbox state.
        requires_admin: True when elevation is necessary to delete.
        command: Optional callable replacing filesystem deletion (e.g. docker prune).
        needs_extra_allowed: Extra path prefixes to grant to the safety guard
            for this item (used when we intentionally touch sub-paths of a
            denied root, e.g. __pycache__ under user Documents).
        size_bytes: Populated by the scanner.
        file_count: Populated by the scanner.
        error: Populated by the scanner when sizing or existence check fails.
    """

    id: str
    name: str
    paths: List[Path]
    risk: Risk
    affects: str
    recreated_automatically: bool = True
    reversible: bool = True
    default_selected: bool = True
    requires_admin: bool = False
    command: Optional[Callable[[], None]] = None
    needs_extra_allowed: List[Path] = field(default_factory=list)

    size_bytes: int = 0
    file_count: int = 0
    error: Optional[str] = None
    detected: bool = False


@dataclass
class ScanReport:
    items: List[CleanItem]

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.items if item.detected)


class Category:
    """Abstract category. Subclasses implement :meth:`build_items`."""

    id: str = "category"
    name: str = "Category"
    description: str = ""
    icon: str = ""

    def __init__(self) -> None:
        self._items: Optional[List[CleanItem]] = None

    def build_items(self) -> Iterable[CleanItem]:
        """Enumerate candidate items for this category.

        Implementations should NOT perform heavy I/O here. Return cheap
        :class:`CleanItem` descriptors - the scanner computes sizes in parallel.
        """
        raise NotImplementedError

    def scan(self) -> List[CleanItem]:
        """Return the cached list of items for this category."""
        if self._items is None:
            self._items = list(self.build_items())
        return self._items

    def reset(self) -> None:
        self._items = None
