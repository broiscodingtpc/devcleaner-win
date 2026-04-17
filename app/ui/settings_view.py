"""Editable settings panel."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from ..core.settings import Settings
from .theme import PALETTE


class SettingsView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        get_settings: Callable[[], Settings],
        save_settings: Callable[[Settings], None],
    ) -> None:
        super().__init__(master, fg_color=PALETTE.bg_card, corner_radius=8)
        self._get = get_settings
        self._save = save_settings

        ctk.CTkLabel(
            self,
            text="Cleaner preferences",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=PALETTE.text,
        ).pack(anchor="w", padx=18, pady=(14, 8))

        self._dry_run = ctk.BooleanVar()
        self._recycle = ctk.BooleanVar()
        self._high_risk = ctk.BooleanVar()
        self._threshold_var = ctk.StringVar()

        self._add_toggle(
            self._dry_run,
            "Dry run",
            "Scan and report what would be deleted without touching the filesystem.",
        )
        self._add_toggle(
            self._recycle,
            "Send to Recycle Bin",
            "When enabled, deletions go to the Recycle Bin so you can restore them. "
            "Turn off for permanent deletion.",
        )
        self._add_toggle(
            self._high_risk,
            "Pre-select HIGH risk items",
            "By default, items marked High are unchecked. Enable to opt in globally.",
        )

        threshold_row = ctk.CTkFrame(self, fg_color="transparent")
        threshold_row.pack(fill="x", padx=18, pady=(10, 4))
        ctk.CTkLabel(
            threshold_row,
            text="Confirm when cleanup exceeds (MB):",
            text_color=PALETTE.text,
        ).pack(side="left")
        ctk.CTkEntry(
            threshold_row,
            textvariable=self._threshold_var,
            width=80,
            fg_color=PALETTE.bg_alt,
            border_color=PALETTE.border,
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            self,
            text="Extra scan roots (for Python artifacts & node_modules)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PALETTE.text,
        ).pack(anchor="w", padx=18, pady=(16, 4))

        self._roots_box = ctk.CTkTextbox(
            self,
            fg_color=PALETTE.bg_alt,
            text_color=PALETTE.text,
            border_color=PALETTE.border,
            border_width=1,
            height=140,
            wrap="none",
        )
        self._roots_box.pack(fill="x", padx=18, pady=(0, 6))

        roots_row = ctk.CTkFrame(self, fg_color="transparent")
        roots_row.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkButton(
            roots_row,
            text="Add folder...",
            fg_color=PALETTE.bg_alt,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            command=self._pick_folder,
            width=120,
        ).pack(side="left")
        ctk.CTkLabel(
            roots_row,
            text="One path per line. Paths are walked recursively (with sensible prunes).",
            text_color=PALETTE.text_muted,
            font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=10)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(12, 14))
        ctk.CTkButton(
            footer,
            text="Save",
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent_hover,
            text_color="white",
            command=self._on_save,
            width=110,
        ).pack(side="right")
        ctk.CTkButton(
            footer,
            text="Reload",
            fg_color=PALETTE.bg_alt,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            command=self.reload,
            width=90,
        ).pack(side="right", padx=10)

        self.reload()

    def _add_toggle(self, var: ctk.BooleanVar, title: str, description: str) -> None:
        row = ctk.CTkFrame(self, fg_color=PALETTE.bg_alt, corner_radius=6)
        row.pack(fill="x", padx=18, pady=4)
        ctk.CTkSwitch(
            row,
            text=title,
            variable=var,
            button_color=PALETTE.accent,
            progress_color=PALETTE.accent,
            fg_color=PALETTE.border,
            text_color=PALETTE.text,
        ).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            row,
            text=description,
            text_color=PALETTE.text_muted,
            wraplength=600,
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def reload(self) -> None:
        settings = self._get()
        self._dry_run.set(settings.dry_run)
        self._recycle.set(settings.use_recycle_bin)
        self._high_risk.set(settings.include_high_risk_by_default)
        self._threshold_var.set(str(settings.confirm_threshold_mb))
        self._roots_box.delete("0.0", "end")
        self._roots_box.insert("0.0", "\n".join(settings.extra_scan_roots))

    def _pick_folder(self) -> None:
        folder = filedialog.askdirectory()
        if not folder:
            return
        existing = self._roots_box.get("0.0", "end").strip().splitlines()
        if folder not in existing:
            existing.append(folder)
        self._roots_box.delete("0.0", "end")
        self._roots_box.insert("0.0", "\n".join(existing))

    def _on_save(self) -> None:
        try:
            threshold = max(0, int(float(self._threshold_var.get() or 0)))
        except ValueError:
            threshold = 500
        raw_roots = self._roots_box.get("0.0", "end").strip().splitlines()
        roots = [str(Path(line).expanduser()) for line in raw_roots if line.strip()]

        current = self._get()
        current.dry_run = bool(self._dry_run.get())
        current.use_recycle_bin = bool(self._recycle.get())
        current.include_high_risk_by_default = bool(self._high_risk.get())
        current.confirm_threshold_mb = threshold
        current.extra_scan_roots = roots
        self._save(current)
