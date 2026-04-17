"""Safe deletion executor.

Processes a list of :class:`CleanItem` objects one at a time, logging every
action, reporting progress to the UI and respecting the user's dry-run /
Recycle Bin preferences.
"""
from __future__ import annotations

import os
import shutil
import stat
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from ..categories.base import CleanItem
from .logger import get_logger
from .safety import UnsafePathError, assert_safe_to_delete
from .settings import Settings
from .sizing import invalidate_size_cache

_log = get_logger()


@dataclass
class CleanupResult:
    item_id: str
    name: str
    freed_bytes: int = 0
    deleted_files: int = 0
    errors: List[str] = field(default_factory=list)
    skipped: bool = False
    reason: str = ""


@dataclass
class CleanupProgress:
    total_items: int
    done_items: int
    total_bytes: int
    freed_bytes: int
    current: Optional[str]


ProgressCallback = Callable[[CleanupProgress], None]
ResultCallback = Callable[[CleanupResult], None]


def _on_rm_error(func, path, exc_info):
    """Retry after flipping the read-only bit (common on Windows junk)."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        raise


def _send_to_trash(path: Path) -> None:
    from send2trash import send2trash

    send2trash(str(path))


class Executor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stop = threading.Event()

    def abort(self) -> None:
        self._stop.set()

    def run(
        self,
        items: List[CleanItem],
        *,
        on_result: Optional[ResultCallback] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[CleanupResult]:
        self._stop.clear()
        results: List[CleanupResult] = []

        total_items = len(items)
        total_bytes = sum(max(0, it.size_bytes) for it in items)
        freed = 0

        _log.info(
            "cleanup: starting %d items (%d bytes total, dry_run=%s, recycle=%s)",
            total_items,
            total_bytes,
            self.settings.dry_run,
            self.settings.use_recycle_bin,
        )

        for index, item in enumerate(items, start=1):
            if self._stop.is_set():
                _log.info("cleanup aborted by user")
                break

            if on_progress is not None:
                try:
                    on_progress(
                        CleanupProgress(
                            total_items=total_items,
                            done_items=index - 1,
                            total_bytes=total_bytes,
                            freed_bytes=freed,
                            current=item.name,
                        )
                    )
                except Exception:
                    pass

            result = self._clean_item(item)
            freed += result.freed_bytes
            results.append(result)

            if on_result is not None:
                try:
                    on_result(result)
                except Exception:
                    pass

            if on_progress is not None:
                try:
                    on_progress(
                        CleanupProgress(
                            total_items=total_items,
                            done_items=index,
                            total_bytes=total_bytes,
                            freed_bytes=freed,
                            current=item.name,
                        )
                    )
                except Exception:
                    pass

        _log.info("cleanup: done, freed %d bytes across %d items", freed, len(results))
        return results

    # -- internals ------------------------------------------------------------

    def _clean_item(self, item: CleanItem) -> CleanupResult:
        result = CleanupResult(item_id=item.id, name=item.name)

        if item.command is not None and not item.paths:
            if self.settings.dry_run:
                _log.info("[dry-run] would execute command for %s", item.name)
                result.freed_bytes = max(0, item.size_bytes)
                return result
            try:
                item.command()
                result.freed_bytes = max(0, item.size_bytes)
            except Exception as exc:
                result.errors.append(str(exc))
                _log.error("command failed for %s: %s", item.name, exc)
            return result

        extra = [Path(e) for e in item.needs_extra_allowed]
        for raw_path in item.paths:
            if self._stop.is_set():
                result.skipped = True
                result.reason = "aborted"
                break

            path = Path(raw_path)
            if not path.exists():
                continue

            try:
                safe_path = assert_safe_to_delete(path, extra_allowed=extra)
            except UnsafePathError as exc:
                msg = f"refused {path}: {exc}"
                result.errors.append(msg)
                _log.warning(msg)
                continue

            if self.settings.dry_run:
                _log.info("[dry-run] would delete %s", safe_path)
                continue

            try:
                freed_here, deleted_here = self._delete_one(safe_path)
                result.freed_bytes += freed_here
                result.deleted_files += deleted_here
                invalidate_size_cache(safe_path)
            except Exception as exc:
                msg = f"failed to delete {safe_path}: {exc}"
                result.errors.append(msg)
                _log.error(msg)

        return result

    def _delete_one(self, path: Path) -> tuple[int, int]:
        """Delete path. Returns (freed_bytes, files_removed)."""
        freed = 0
        files = 0
        try:
            if path.is_file() or path.is_symlink():
                try:
                    freed = path.stat().st_size
                except OSError:
                    pass
                files = 1
                if self.settings.use_recycle_bin:
                    _send_to_trash(path)
                else:
                    try:
                        path.unlink()
                    except PermissionError:
                        os.chmod(path, stat.S_IWRITE)
                        path.unlink()
                return freed, files

            # Directory: size up first so we can report freed bytes.
            for root, _dirs, filenames in os.walk(path):
                for fname in filenames:
                    fpath = os.path.join(root, fname)
                    try:
                        freed += os.stat(fpath, follow_symlinks=False).st_size
                        files += 1
                    except OSError:
                        pass

            if self.settings.use_recycle_bin:
                _send_to_trash(path)
            else:
                shutil.rmtree(path, onerror=_on_rm_error)
            return freed, files
        except FileNotFoundError:
            return 0, 0
