"""Side panel showing the 'what will this affect' explanation for a selected item."""
from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..categories.base import CleanItem
from ..core.sizing import human_bytes
from .theme import PALETTE, RISK_COLORS


class DetailPanel(ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master, fg_color=PALETTE.bg_card, corner_radius=8)

        ctk.CTkLabel(
            self,
            text="What will this affect?",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE.text,
        ).pack(anchor="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            self,
            text="Click an item on the left to preview the impact.",
            font=ctk.CTkFont(size=11),
            text_color=PALETTE.text_muted,
        ).pack(anchor="w", padx=14, pady=(0, 10))

        self._name = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=PALETTE.text,
            wraplength=360,
            justify="left",
            anchor="w",
        )
        self._name.pack(fill="x", padx=14, pady=(4, 6))

        self._badges = ctk.CTkFrame(self, fg_color="transparent")
        self._badges.pack(fill="x", padx=14, pady=(0, 8))

        self._risk_badge = ctk.CTkLabel(
            self._badges,
            text="",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            corner_radius=4,
            width=70,
            height=22,
        )
        self._admin_badge = ctk.CTkLabel(
            self._badges,
            text="",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            corner_radius=4,
            height=22,
        )
        self._reversible_badge = ctk.CTkLabel(
            self._badges,
            text="",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            corner_radius=4,
            height=22,
        )

        self._size_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=PALETTE.accent,
        )
        self._size_label.pack(anchor="w", padx=14, pady=(2, 8))

        ctk.CTkLabel(
            self,
            text="Impact",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=PALETTE.text_muted,
        ).pack(anchor="w", padx=14, pady=(4, 0))
        self._affects = ctk.CTkLabel(
            self,
            text="",
            text_color=PALETTE.text,
            wraplength=360,
            justify="left",
            anchor="w",
        )
        self._affects.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="Paths",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=PALETTE.text_muted,
        ).pack(anchor="w", padx=14, pady=(6, 0))

        self._paths_box = ctk.CTkTextbox(
            self,
            fg_color=PALETTE.bg_alt,
            text_color=PALETTE.text,
            height=240,
            border_color=PALETTE.border,
            border_width=1,
            wrap="none",
        )
        self._paths_box.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self._paths_box.configure(state="disabled")

    def show(self, item: Optional[CleanItem]) -> None:
        if item is None:
            self._name.configure(text="")
            self._affects.configure(text="")
            self._size_label.configure(text="")
            self._risk_badge.pack_forget()
            self._admin_badge.pack_forget()
            self._reversible_badge.pack_forget()
            self._paths_box.configure(state="normal")
            self._paths_box.delete("0.0", "end")
            self._paths_box.configure(state="disabled")
            return

        self._name.configure(text=item.name)
        self._size_label.configure(
            text=(
                f"Reclaims ~{human_bytes(item.size_bytes)}"
                if item.size_bytes
                else ("Command action" if item.command else "Empty")
            )
        )

        color = RISK_COLORS.get(item.risk.value, PALETTE.text_muted)
        self._risk_badge.configure(text=f"RISK: {item.risk.value.upper()}", fg_color=color)
        self._risk_badge.pack(side="left", padx=(0, 6))

        if item.requires_admin:
            self._admin_badge.configure(text="NEEDS ADMIN", fg_color=PALETTE.warning)
            self._admin_badge.pack(side="left", padx=(0, 6))
        else:
            self._admin_badge.pack_forget()

        self._reversible_badge.configure(
            text=("REVERSIBLE" if item.reversible else "PERMANENT"),
            fg_color=PALETTE.info if item.reversible else PALETTE.danger,
        )
        self._reversible_badge.pack(side="left")

        recreated = (
            "Recreated automatically. "
            if item.recreated_automatically
            else "Will not come back unless you recreate it. "
        )
        self._affects.configure(text=recreated + item.affects)

        self._paths_box.configure(state="normal")
        self._paths_box.delete("0.0", "end")
        if item.paths:
            lines = [str(p) for p in item.paths]
            self._paths_box.insert("0.0", "\n".join(lines))
        elif item.command:
            self._paths_box.insert("0.0", "(executes a command - no filesystem paths)")
        self._paths_box.configure(state="disabled")
