"""WinCleaner - application entry point.

Run directly with `python main.py` or launch the pre-built executable. The
app works without admin privileges, but some categories (Windows Update
cache, Prefetch, SoftwareDistribution...) need elevation and will be skipped
otherwise.
"""
from __future__ import annotations

import sys


def _check_python_version() -> None:
    if sys.version_info < (3, 10):
        sys.stderr.write(
            "WinCleaner requires Python 3.10 or newer. Current: "
            f"{sys.version.split()[0]}\n"
        )
        sys.exit(1)


def main() -> int:
    _check_python_version()
    try:
        from app.ui.app import run
    except ImportError as exc:
        sys.stderr.write(f"Failed to import UI: {exc}\n")
        sys.stderr.write("Did you run `pip install -r requirements.txt`?\n")
        return 2

    try:
        run()
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
