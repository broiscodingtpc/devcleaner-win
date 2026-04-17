"""Fast directory sizing utilities."""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional


@dataclass(frozen=True)
class SizeResult:
    path: Path
    bytes_: int
    files: int
    error: Optional[str] = None


_cache: dict[str, SizeResult] = {}
_cache_lock = threading.Lock()


def human_bytes(n: int) -> str:
    if n is None:
        return "-"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def compute_size(path: Path, *, follow_symlinks: bool = False) -> SizeResult:
    """Compute the size of *path* recursively.

    Errors on individual entries are swallowed; the result reports the
    summed size of everything we were able to stat.
    """
    total = 0
    files = 0
    first_error: Optional[str] = None

    if not path.exists():
        return SizeResult(path=path, bytes_=0, files=0, error="missing")

    if path.is_file() or path.is_symlink():
        try:
            total = path.stat().st_size
            files = 1
        except OSError as exc:
            first_error = str(exc)
        return SizeResult(path=path, bytes_=total, files=files, error=first_error)

    try:
        for root, dirs, filenames in os.walk(path, followlinks=follow_symlinks):
            for fname in filenames:
                fpath = os.path.join(root, fname)
                try:
                    st = os.stat(fpath, follow_symlinks=False)
                    total += st.st_size
                    files += 1
                except OSError as exc:
                    if first_error is None:
                        first_error = str(exc)
    except OSError as exc:
        first_error = str(exc)

    return SizeResult(path=path, bytes_=total, files=files, error=first_error)


def compute_size_cached(path: Path) -> SizeResult:
    key = str(path)
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached
    result = compute_size(path)
    with _cache_lock:
        _cache[key] = result
    return result


def invalidate_size_cache(path: Path | None = None) -> None:
    with _cache_lock:
        if path is None:
            _cache.clear()
        else:
            _cache.pop(str(path), None)


def compute_sizes_parallel(
    paths: Iterable[Path],
    *,
    workers: int = 8,
    progress: Optional[Callable[[SizeResult], None]] = None,
) -> list[SizeResult]:
    unique = []
    seen: set[str] = set()
    for p in paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    results: list[SizeResult] = []
    if not unique:
        return results

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for result in pool.map(compute_size_cached, unique):
            results.append(result)
            if progress is not None:
                try:
                    progress(result)
                except Exception:
                    pass
    return results
