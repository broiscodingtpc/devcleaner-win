"""UI for the localhost server list."""
from __future__ import annotations

import threading
from tkinter import messagebox
from typing import Callable, List

import customtkinter as ctk

from ..net.ports import PortEntry, format_uptime, kill_process, list_listening_ports
from .theme import PALETTE


class PortsView(ctk.CTkFrame):
    def __init__(self, master, *, on_status: Callable[[str], None]) -> None:
        super().__init__(master, fg_color=PALETTE.bg_card, corner_radius=8)
        self.on_status = on_status
        self._rows: List[ctk.CTkFrame] = []
        self._entries: List[PortEntry] = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            header,
            text="Listening ports",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE.text,
        ).pack(side="left")

        btn_container = ctk.CTkFrame(header, fg_color="transparent")
        btn_container.pack(side="right")
        ctk.CTkButton(
            btn_container,
            text="Refresh",
            width=90,
            height=24,
            fg_color=PALETTE.bg_alt,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            command=self.refresh,
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            btn_container,
            text="Kill forgotten",
            width=120,
            height=24,
            fg_color=PALETTE.danger,
            hover_color=PALETTE.accent_hover,
            text_color="white",
            command=self._kill_forgotten,
        ).pack(side="left")

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=PALETTE.bg_alt, corner_radius=6
        )
        self._scroll.pack(fill="both", expand=True, padx=8, pady=(4, 10))

    def refresh(self) -> None:
        self.on_status("Scanning listening ports...")
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        loading = ctk.CTkLabel(
            self._scroll,
            text="Scanning ports...",
            text_color=PALETTE.text_muted,
        )
        loading.pack(pady=20)
        self._rows.append(loading)

        def task() -> None:
            try:
                entries = list_listening_ports()
            except Exception as exc:
                self.after(0, self._render_error, str(exc))
                return
            self.after(0, self._render, entries)

        threading.Thread(target=task, daemon=True, name="ports-scan").start()

    def _render_error(self, message: str) -> None:
        for row in self._rows:
            row.destroy()
        self._rows.clear()
        lbl = ctk.CTkLabel(self._scroll, text=f"Error: {message}", text_color=PALETTE.danger)
        lbl.pack(pady=20)
        self._rows.append(lbl)
        self.on_status("Port scan failed")

    def _render(self, entries: List[PortEntry]) -> None:
        self._entries = entries
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        if not entries:
            lbl = ctk.CTkLabel(
                self._scroll,
                text="No listening TCP sockets detected on localhost.",
                text_color=PALETTE.text_muted,
            )
            lbl.pack(pady=20)
            self._rows.append(lbl)
            self.on_status("Ready")
            return

        for entry in entries:
            row = self._build_row(entry)
            row.pack(fill="x", padx=4, pady=3)
            self._rows.append(row)
        forgotten = sum(1 for e in entries if e.likely_forgotten)
        self.on_status(f"{len(entries)} listeners, {forgotten} flagged as forgotten")

    def _build_row(self, entry: PortEntry) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self._scroll, fg_color=PALETTE.bg_card, corner_radius=6)
        row.grid_columnconfigure(3, weight=1)

        if entry.likely_forgotten:
            tag_color = PALETTE.warning
            tag_text = "FORGOTTEN"
        elif entry.is_system:
            tag_color = PALETTE.info
            tag_text = "SYSTEM"
        else:
            tag_color = PALETTE.accent
            tag_text = "ACTIVE"

        badge = ctk.CTkLabel(
            row,
            text=tag_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            fg_color=tag_color,
            corner_radius=4,
            width=80,
            height=22,
        )
        badge.grid(row=0, column=0, padx=10, pady=8)

        port_label = ctk.CTkLabel(
            row,
            text=f"{entry.address}:{entry.port}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE.text,
        )
        port_label.grid(row=0, column=1, padx=(0, 12), pady=8, sticky="w")

        name_label = ctk.CTkLabel(
            row,
            text=f"{entry.name} (PID {entry.pid})",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE.text,
        )
        name_label.grid(row=0, column=2, padx=(0, 12), pady=(8, 0), sticky="w")

        info_text = (
            f"uptime {format_uptime(entry.uptime_seconds)}  user {entry.username}  "
            f"parent {entry.parent_name or '-'}"
        )
        if entry.forgotten_reason:
            info_text += f"  reason: {entry.forgotten_reason}"
        info = ctk.CTkLabel(
            row,
            text=info_text,
            font=ctk.CTkFont(size=10),
            text_color=PALETTE.text_muted,
        )
        info.grid(row=1, column=1, columnspan=3, padx=0, pady=(0, 2), sticky="w")

        cmd_text = entry.cmdline or entry.exe or "-"
        if len(cmd_text) > 160:
            cmd_text = cmd_text[:157] + "..."
        cmd = ctk.CTkLabel(
            row,
            text=cmd_text,
            font=ctk.CTkFont(size=10),
            text_color=PALETTE.text_muted,
            wraplength=700,
            justify="left",
            anchor="w",
        )
        cmd.grid(row=2, column=1, columnspan=3, padx=0, pady=(0, 6), sticky="w")

        kill_btn = ctk.CTkButton(
            row,
            text="Kill",
            width=70,
            height=26,
            fg_color=PALETTE.danger,
            hover_color=PALETTE.accent_hover,
            text_color="white",
            state=("disabled" if entry.is_system else "normal"),
            command=lambda p=entry.pid: self._kill_single(p),
        )
        kill_btn.grid(row=0, column=4, padx=10, pady=8)

        return row

    def _kill_single(self, pid: int) -> None:
        if pid <= 0:
            return
        if not messagebox.askyesno(
            "Kill process", f"Terminate process with PID {pid}?"
        ):
            return
        ok, message = kill_process(pid)
        if not ok:
            messagebox.showerror("Kill failed", message)
        self.refresh()

    def _kill_forgotten(self) -> None:
        candidates = [e for e in self._entries if e.likely_forgotten and not e.is_system]
        if not candidates:
            messagebox.showinfo("Nothing to kill", "No processes flagged as forgotten.")
            return
        if not messagebox.askyesno(
            "Kill forgotten",
            f"Terminate {len(candidates)} forgotten listener process(es)?",
        ):
            return
        errors: List[str] = []
        for entry in candidates:
            ok, message = kill_process(entry.pid)
            if not ok:
                errors.append(f"{entry.name} (PID {entry.pid}): {message}")
        if errors:
            messagebox.showwarning("Some processes survived", "\n".join(errors))
        self.refresh()
