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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from ..categories.base import CleanItem
from .logger import get_logger
from .pathwin import extended_length_str, format_os_error
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
    try:
        from send2trash import send2trash
    except ImportError as exc:
        raise RuntimeError(
            "send2trash is not installed. Run: pip install send2trash"
        ) from exc
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
                freed_here, deleted_here = self._delete_one(
                    safe_path,
                    contents_only=item.contents_only,
                    direct_delete=item.direct_delete,
                )
                result.freed_bytes += freed_here
                result.deleted_files += deleted_here
                invalidate_size_cache(safe_path)
            except Exception as exc:
                msg = f"failed to delete {safe_path}: {format_os_error(exc) if isinstance(exc, OSError) else exc}"
                result.errors.append(msg)
                _log.error(msg)

        return result

    def _unlink_forced(self, path: Path) -> None:
        """Remove a file or symlink; chmod retry on Windows."""
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            try:
                os.chmod(path, stat.S_IWRITE)
                path.unlink(missing_ok=True)
            except OSError:
                if os.name == "nt":
                    os.unlink(extended_length_str(path))
                else:
                    raise

    def _rmtree_forced(self, path: Path) -> None:
        """Remove a directory tree; prefer extended-length paths on Windows."""
        target = extended_length_str(path) if os.name == "nt" else str(path)
        shutil.rmtree(target, onerror=_on_rm_error)

    def _delete_contents_children(
        self,
        children: List[Path],
        *,
        direct_delete: bool,
    ) -> tuple[int, int]:
        """Delete top-level entries under a contents_only folder (optionally parallel)."""
        if not children:
            return 0, 0

        use_parallel = direct_delete and len(children) > 3
        if not use_parallel:
            total_freed = 0
            total_files = 0
            for child in children:
                if self._stop.is_set():
                    break
                try:
                    f, n = self._delete_one(
                        child, contents_only=False, direct_delete=direct_delete
                    )
                    total_freed += f
                    total_files += n
                except Exception as exc:
                    _log.warning("skip %s: %s", child, exc)
            return total_freed, total_files

        workers = min(32, max(4, (os.cpu_count() or 4) * 2), len(children))
        total_freed = 0
        total_files = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {
                pool.submit(
                    self._delete_one,
                    child,
                    contents_only=False,
                    direct_delete=direct_delete,
                ): child
                for child in children
            }
            for fut in as_completed(future_map):
                if self._stop.is_set():
                    break
                child = future_map[fut]
                try:
                    f, n = fut.result()
                    total_freed += f
                    total_files += n
                except Exception as exc:
                    _log.warning("skip %s: %s", child, exc)
        return total_freed, total_files

    def _delete_one(
        self,
        path: Path,
        *,
        contents_only: bool = False,
        direct_delete: bool = False,
    ) -> tuple[int, int]:
        """Delete path. Returns (freed_bytes, files_removed).

        *contents_only*: delete everything inside *path* but keep *path* itself.
        Used for %TEMP% and similar — Windows Shell refuses to recycle the root folder (OLE 0x80270028).

        *direct_delete*: skip send2trash entirely (no Shell / OLE per file). Much faster for
        Temp and $Recycle.Bin; not recoverable from Explorer's Recycle Bin.

        Symlinks (file or directory) remove only the link, never the target tree.
        """
        try:
            path = path.resolve()
        except OSError:
            path = path

        use_trash = self.settings.use_recycle_bin and not direct_delete

        try:
            if contents_only and path.is_dir() and not path.is_symlink():
                try:
                    children = list(path.iterdir())
                except OSError as exc:
                    _log.warning("cannot list %s: %s", path, exc)
                    return 0, 0
                return self._delete_contents_children(
                    children, direct_delete=direct_delete
                )

            # Symlink (to file or dir): never follow into target
            if path.is_symlink():
                freed = 0
                try:
                    freed = path.stat().st_size
                except OSError:
                    pass
                files = 1
                if use_trash:
                    try:
                        _send_to_trash(path)
                    except Exception as exc:
                        _log.warning("send2trash failed for symlink %s: %s", path, exc)
                        self._unlink_forced(path)
                else:
                    self._unlink_forced(path)
                return freed, files

            freed = 0
            files = 0
            if path.is_file():
                try:
                    freed = path.stat().st_size
                except OSError:
                    pass
                files = 1
                if use_trash:
                    try:
                        _send_to_trash(path)
                    except Exception as exc:
                        _log.warning("send2trash failed for file %s: %s", path, exc)
                        self._unlink_forced(path)
                else:
                    self._unlink_forced(path)
                return freed, files

            # Real directory (not a symlink)
            for root, _dirs, filenames in os.walk(path, topdown=False, followlinks=False):
                for fname in filenames:
                    fpath = os.path.join(root, fname)
                    try:
                        freed += os.stat(fpath, follow_symlinks=False).st_size
                        files += 1
                    except OSError:
                        pass

            if use_trash:
                try:
                    _send_to_trash(path)
                except Exception as exc:
                    _log.warning(
                        "send2trash failed for dir %s (%s); falling back to direct delete",
                        path,
                        exc,
                    )
                    self._rmtree_forced(path)
            else:
                self._rmtree_forced(path)
            return freed, files
        except FileNotFoundError:
            return 0, 0
