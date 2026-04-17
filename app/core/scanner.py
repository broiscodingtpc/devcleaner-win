"""High level scan orchestration.

Each category contributes :class:`CleanItem` objects; the scanner feeds every
path into a thread pool to compute sizes. Results are streamed via callbacks
so the UI can update progressively.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from ..categories.base import Category, CleanItem, ScanReport
from .logger import get_logger
from .sizing import compute_size_cached

_log = get_logger()


@dataclass
class ScanProgress:
    total: int
    done: int
    current: Optional[CleanItem]


ScanCallback = Callable[[ScanProgress], None]
ItemCallback = Callable[[CleanItem], None]


class Scanner:
    def __init__(self, categories: Iterable[Category]) -> None:
        self.categories = list(categories)
        self._stop = threading.Event()

    def abort(self) -> None:
        self._stop.set()

    def run(
        self,
        *,
        on_item: Optional[ItemCallback] = None,
        on_progress: Optional[ScanCallback] = None,
    ) -> ScanReport:
        self._stop.clear()
        all_items: List[CleanItem] = []
        for cat in self.categories:
            try:
                all_items.extend(cat.scan())
            except Exception as exc:
                _log.error("category %s failed to enumerate: %s", cat.id, exc)

        total = len(all_items)
        _log.info("scan: %d items enumerated", total)

        for index, item in enumerate(all_items, start=1):
            if self._stop.is_set():
                _log.info("scan aborted by user")
                break
            self._size_item(item)
            if on_item is not None:
                try:
                    on_item(item)
                except Exception as exc:
                    _log.warning("scan callback failed: %s", exc)
            if on_progress is not None:
                try:
                    on_progress(ScanProgress(total=total, done=index, current=item))
                except Exception:
                    pass

        return ScanReport(items=all_items)

    def _size_item(self, item: CleanItem) -> None:
        if item.command is not None and not item.paths:
            item.detected = True
            return

        total_bytes = 0
        total_files = 0
        existed = False
        errors: List[str] = []

        for path in item.paths:
            if not isinstance(path, Path):
                path = Path(path)
            try:
                if not path.exists():
                    continue
                existed = True
                res = compute_size_cached(path)
                total_bytes += res.bytes_
                total_files += res.files
                if res.error:
                    errors.append(res.error)
            except Exception as exc:
                errors.append(str(exc))

        item.size_bytes = total_bytes
        item.file_count = total_files
        item.detected = existed or item.command is not None
        if errors:
            item.error = "; ".join(errors[:3])
