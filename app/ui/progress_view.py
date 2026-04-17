"""Modal progress dialog shown while the executor is running."""
from __future__ import annotations

from typing import Callable, List, Optional

import customtkinter as ctk

from ..core.executor import CleanupProgress, CleanupResult
from ..core.sizing import human_bytes
from .theme import PALETTE


class ProgressDialog(ctk.CTkToplevel):
    def __init__(self, master, *, title: str = "Cleaning") -> None:
        super().__init__(master)
        self.title(title)
        self.geometry("620x420")
        self.configure(fg_color=PALETTE.bg)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.on_cancel: Optional[Callable[[], None]] = None
        self._finished = False

        self._status_label = ctk.CTkLabel(
            self,
            text="Preparing...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=PALETTE.text,
        )
        self._status_label.pack(anchor="w", padx=18, pady=(16, 4))

        self._progress = ctk.CTkProgressBar(
            self, progress_color=PALETTE.accent, fg_color=PALETTE.bg_alt
        )
        self._progress.pack(fill="x", padx=18, pady=(0, 8))
        self._progress.set(0)

        self._detail = ctk.CTkLabel(
            self,
            text="0 / 0 items - 0 B freed",
            font=ctk.CTkFont(size=11),
            text_color=PALETTE.text_muted,
        )
        self._detail.pack(anchor="w", padx=18, pady=(0, 8))

        self._log = ctk.CTkTextbox(
            self,
            fg_color=PALETTE.bg_alt,
            text_color=PALETTE.text,
            border_color=PALETTE.border,
            border_width=1,
            wrap="word",
        )
        self._log.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        self._log.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(0, 14))

        self._cancel_btn = ctk.CTkButton(
            footer,
            text="Cancel",
            fg_color=PALETTE.bg_card,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            command=self._cancel,
            width=90,
        )
        self._cancel_btn.pack(side="right")

        self._close_btn = ctk.CTkButton(
            footer,
            text="Close",
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent_hover,
            text_color="white",
            command=self.destroy,
            width=90,
            state="disabled",
        )
        self._close_btn.pack(side="right", padx=(0, 8))

    def _append(self, level: str, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", f"[{level}] {text}\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def update_progress(self, progress: CleanupProgress) -> None:
        if progress.total_items:
            self._progress.set(progress.done_items / progress.total_items)
        status = (
            f"{progress.done_items}/{progress.total_items} items - freed "
            f"{human_bytes(progress.freed_bytes)} of ~{human_bytes(progress.total_bytes)}"
        )
        self._detail.configure(text=status)
        if progress.current:
            self._status_label.configure(text=f"Cleaning: {progress.current}")

    def append_result(self, result: CleanupResult) -> None:
        if result.errors:
            for err in result.errors:
                self._append("ERR", err)
        self._append(
            "OK",
            f"{result.name} - freed {human_bytes(result.freed_bytes)}"
            + (f" ({result.deleted_files} files)" if result.deleted_files else ""),
        )

    def finish(self, results: List[CleanupResult], total_freed: int) -> None:
        self._finished = True
        self._progress.set(1)
        errors = sum(1 for r in results if r.errors)
        self._status_label.configure(
            text=f"Done - freed {human_bytes(total_freed)} across {len(results)} items"
            + (f" ({errors} with errors)" if errors else "")
        )
        self._cancel_btn.configure(state="disabled")
        self._close_btn.configure(state="normal")

    def fail(self, message: str) -> None:
        self._finished = True
        self._append("FATAL", message)
        self._status_label.configure(text=f"Failed: {message}", text_color=PALETTE.danger)
        self._cancel_btn.configure(state="disabled")
        self._close_btn.configure(state="normal")

    def _cancel(self) -> None:
        if self._finished:
            self.destroy()
            return
        self._append("INFO", "Cancellation requested...")
        self._cancel_btn.configure(state="disabled")
        if self.on_cancel:
            try:
                self.on_cancel()
            except Exception:
                pass

    def _on_close(self) -> None:
        if self._finished:
            self.destroy()
        else:
            self._cancel()
