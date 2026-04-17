"""Scrollable list of cleanable items with checkbox + risk badge."""
from __future__ import annotations

from typing import Callable, Dict, List

import customtkinter as ctk

from ..categories.base import CleanItem
from ..core.sizing import human_bytes
from .theme import PALETTE


class ScanView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        on_toggle: Callable[[str], None],
        on_select: Callable[[str], None],
    ) -> None:
        super().__init__(master, fg_color=PALETTE.bg_card, corner_radius=8)
        self.on_toggle = on_toggle
        self.on_select = on_select

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            header,
            text="Select items to clean",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE.text,
        ).pack(side="left")

        btn_container = ctk.CTkFrame(header, fg_color="transparent")
        btn_container.pack(side="right")
        ctk.CTkButton(
            btn_container,
            text="Select all",
            width=80,
            height=24,
            fg_color=PALETTE.bg_alt,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            command=self._select_all,
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            btn_container,
            text="Clear",
            width=60,
            height=24,
            fg_color=PALETTE.bg_alt,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            command=self._clear_all,
        ).pack(side="left")

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=PALETTE.bg_alt, corner_radius=6
        )
        self._scroll.pack(fill="both", expand=True, padx=8, pady=(4, 10))

        self._rows: List[ctk.CTkFrame] = []
        self._checks: Dict[str, ctk.BooleanVar] = {}

    def _select_all(self) -> None:
        for var in self._checks.values():
            var.set(True)

    def _clear_all(self) -> None:
        for var in self._checks.values():
            var.set(False)

    def render(
        self,
        items: List[CleanItem],
        *,
        checks: Dict[str, ctk.BooleanVar],
        risk_colors: Dict[str, str],
    ) -> None:
        for row in self._rows:
            row.destroy()
        self._rows.clear()
        self._checks = checks

        if not items:
            empty = ctk.CTkLabel(
                self._scroll,
                text="Nothing to show. Try running a scan first.",
                text_color=PALETTE.text_muted,
            )
            empty.pack(pady=40)
            self._rows.append(empty)
            return

        for item in items:
            row = ctk.CTkFrame(self._scroll, fg_color=PALETTE.bg_card, corner_radius=6)
            row.pack(fill="x", padx=4, pady=3)
            row.grid_columnconfigure(2, weight=1)

            var = checks.setdefault(item.id, ctk.BooleanVar(value=item.default_selected))
            chk = ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                width=22,
                checkbox_width=18,
                checkbox_height=18,
                fg_color=PALETTE.accent,
                hover_color=PALETTE.accent_hover,
                border_color=PALETTE.border,
                command=lambda iid=item.id: self.on_toggle(iid),
            )
            chk.grid(row=0, column=0, padx=(10, 6), pady=8, sticky="w")

            badge_color = risk_colors.get(item.risk.value, PALETTE.text_muted)
            badge = ctk.CTkLabel(
                row,
                text=item.risk.value.upper(),
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="white",
                fg_color=badge_color,
                corner_radius=4,
                width=60,
                height=20,
            )
            badge.grid(row=0, column=1, padx=(0, 10), pady=8, sticky="w")

            name = ctk.CTkLabel(
                row,
                text=item.name + ("  (admin)" if item.requires_admin else ""),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=PALETTE.text,
                anchor="w",
                justify="left",
            )
            name.grid(row=0, column=2, sticky="w", pady=(8, 0))

            size_text = human_bytes(item.size_bytes) if item.size_bytes else (
                "ready" if item.command else "0 B"
            )
            size = ctk.CTkLabel(
                row,
                text=size_text,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=PALETTE.accent,
            )
            size.grid(row=0, column=3, padx=12, pady=(8, 0), sticky="e")

            path_text = ""
            if item.paths:
                path_text = str(item.paths[0])
                if len(item.paths) > 1:
                    path_text += f"  (+{len(item.paths) - 1} more)"
            elif item.command:
                path_text = "command"
            desc = ctk.CTkLabel(
                row,
                text=path_text,
                font=ctk.CTkFont(size=10),
                text_color=PALETTE.text_muted,
                anchor="w",
                justify="left",
            )
            desc.grid(row=1, column=2, columnspan=2, sticky="w", padx=0, pady=(0, 8))

            for widget in (row, name, desc, badge, size):
                widget.bind("<Button-1>", lambda _e, iid=item.id: self.on_select(iid))

            self._rows.append(row)
