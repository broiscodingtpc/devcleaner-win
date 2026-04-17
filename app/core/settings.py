"""Persistent user preferences stored as JSON in the app data folder."""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .logger import app_data_dir, get_logger

_log = get_logger()
_settings_lock = threading.Lock()


SETTINGS_FILE = app_data_dir() / "settings.json"


@dataclass
class Settings:
    dry_run: bool = False
    use_recycle_bin: bool = True
    confirm_threshold_mb: int = 500
    extra_scan_roots: List[str] = field(default_factory=list)
    disabled_items: List[str] = field(default_factory=list)
    theme: str = "dark"
    include_high_risk_by_default: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        safe = {k: v for k, v in data.items() if k in allowed}
        return cls(**safe)


_settings_cache: Settings | None = None


def load_settings() -> Settings:
    global _settings_cache
    with _settings_lock:
        if _settings_cache is not None:
            return _settings_cache
        if SETTINGS_FILE.exists():
            try:
                raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                _settings_cache = Settings.from_dict(raw)
            except Exception as exc:
                _log.warning("failed to load settings (%s), using defaults", exc)
                _settings_cache = Settings()
        else:
            _settings_cache = Settings()
        return _settings_cache


def save_settings(settings: Settings) -> None:
    global _settings_cache
    with _settings_lock:
        _settings_cache = settings
        try:
            SETTINGS_FILE.write_text(settings.to_json(), encoding="utf-8")
        except Exception as exc:
            _log.error("failed to save settings: %s", exc)
