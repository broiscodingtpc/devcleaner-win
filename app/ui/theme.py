"""Shared colors, fonts, spacing for the UI."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg: str = "#0F1115"
    bg_alt: str = "#151923"
    bg_card: str = "#1C2130"
    border: str = "#2A3040"
    text: str = "#E6E8EE"
    text_muted: str = "#8A93A6"
    accent: str = "#4CC38A"
    accent_hover: str = "#3FA775"
    danger: str = "#E06A6A"
    warning: str = "#E8B959"
    info: str = "#6AA9E0"
    risk_safe: str = "#4CC38A"
    risk_low: str = "#6AA9E0"
    risk_medium: str = "#E8B959"
    risk_high: str = "#E06A6A"


PALETTE = Palette()


RISK_COLORS = {
    "Safe": PALETTE.risk_safe,
    "Low": PALETTE.risk_low,
    "Medium": PALETTE.risk_medium,
    "High": PALETTE.risk_high,
}
