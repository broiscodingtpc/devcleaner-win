"""Main application window - CustomTkinter."""
from __future__ import annotations

import threading
from pathlib import Path
from tkinter import messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from .. import __version__
from ..categories import all_categories
from ..categories.base import CleanItem, Category, RISK_ORDER, Risk
from ..core.admin import is_admin, relaunch_as_admin
from ..core.executor import CleanupProgress, CleanupResult, Executor
from ..core.logger import app_data_dir, get_logger, register_ui_observer
from ..core.scanner import ScanProgress, Scanner
from ..core.settings import Settings, load_settings, save_settings
from ..core.sizing import human_bytes
from .theme import PALETTE, RISK_COLORS
from .scan_view import ScanView
from .detail_panel import DetailPanel
from .ports_view import PortsView
from .progress_view import ProgressDialog

_log = get_logger()


class CleanerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"WinCleaner - AI Dev Edition v{__version__}")
        self.geometry("1280x820")
        self.minsize(1100, 700)
        self.configure(fg_color=PALETTE.bg)

        self._categories: List[Category] = all_categories()
        self._items: List[CleanItem] = []
        self._checks: Dict[str, ctk.BooleanVar] = {}
        self._selected_item: Optional[CleanItem] = None
        self._active_category_id: str = "all"
        self._search_text: str = ""
        self._scanner: Optional[Scanner] = None
        self._scan_thread: Optional[threading.Thread] = None

        self._build_layout()
        self._refresh_header()
        register_ui_observer(self._on_log)

        self.after(250, self._auto_scan_prompt)

    # ------------------------------------------------------------------ layout
    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self._build_header()
        self._build_main_area()
        self._build_status_bar()

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=PALETTE.bg_alt)
        sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        sidebar.grid_rowconfigure(99, weight=1)

        title = ctk.CTkLabel(
            sidebar,
            text="WinCleaner",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE.text,
        )
        title.grid(row=0, column=0, padx=20, pady=(20, 4), sticky="w")

        subtitle = ctk.CTkLabel(
            sidebar,
            text="AI Dev Edition",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE.text_muted,
        )
        subtitle.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        admin_label = ctk.CTkLabel(
            sidebar,
            text=("Running as Administrator" if is_admin() else "Not Administrator"),
            text_color=PALETTE.accent if is_admin() else PALETTE.warning,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        admin_label.grid(row=2, column=0, padx=20, pady=(0, 6), sticky="w")

        if not is_admin():
            elevate = ctk.CTkButton(
                sidebar,
                text="Relaunch as Admin",
                command=self._elevate,
                fg_color=PALETTE.bg_card,
                hover_color=PALETTE.border,
                text_color=PALETTE.text,
                height=28,
            )
            elevate.grid(row=3, column=0, padx=20, pady=(0, 16), sticky="ew")

        self._nav_buttons: Dict[str, ctk.CTkButton] = {}

        nav_entries = [("all", "All categories")] + [(c.id, c.name) for c in self._categories]
        nav_entries.append(("__ports__", "Localhost servers"))
        nav_entries.append(("__settings__", "Settings"))

        row = 10
        for nid, label in nav_entries:
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                command=lambda n=nid: self._activate_nav(n),
                fg_color="transparent",
                hover_color=PALETTE.bg_card,
                text_color=PALETTE.text,
                anchor="w",
                height=34,
                corner_radius=6,
            )
            btn.grid(row=row, column=0, padx=12, pady=2, sticky="ew")
            self._nav_buttons[nid] = btn
            row += 1

        footer = ctk.CTkLabel(
            sidebar,
            text=f"Logs: {app_data_dir()}",
            text_color=PALETTE.text_muted,
            font=ctk.CTkFont(size=10),
            wraplength=200,
            justify="left",
        )
        footer.grid(row=100, column=0, padx=16, pady=10, sticky="sw")

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, height=88, corner_radius=0, fg_color=PALETTE.bg_alt)
        header.grid(row=0, column=1, columnspan=2, sticky="nsew")
        header.grid_columnconfigure(1, weight=1)

        self._title_label = ctk.CTkLabel(
            header,
            text="All categories",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETTE.text,
        )
        self._title_label.grid(row=0, column=0, padx=20, pady=(16, 0), sticky="w")

        self._subtitle_label = ctk.CTkLabel(
            header,
            text="Click Scan to compute sizes",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE.text_muted,
        )
        self._subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        self._search = ctk.CTkEntry(
            header,
            placeholder_text="Search...",
            width=220,
            fg_color=PALETTE.bg_card,
            border_color=PALETTE.border,
            text_color=PALETTE.text,
        )
        self._search.grid(row=0, column=1, padx=8, pady=(20, 0), sticky="e")
        self._search.bind("<KeyRelease>", self._on_search)

        self._selected_label = ctk.CTkLabel(
            header,
            text="Selected: 0 B",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PALETTE.accent,
        )
        self._selected_label.grid(row=1, column=1, padx=8, pady=(0, 12), sticky="e")

        self._scan_btn = ctk.CTkButton(
            header,
            text="Scan",
            command=self._start_scan,
            fg_color=PALETTE.bg_card,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            width=100,
        )
        self._scan_btn.grid(row=0, column=2, rowspan=2, padx=(6, 6), pady=20, sticky="e")

        self._quick_btn = ctk.CTkButton(
            header,
            text="Quick Clean",
            command=self._quick_clean,
            fg_color=PALETTE.info,
            hover_color=PALETTE.accent_hover,
            text_color="white",
            width=120,
        )
        self._quick_btn.grid(row=0, column=3, rowspan=2, padx=(0, 6), pady=20, sticky="e")

        self._clean_btn = ctk.CTkButton(
            header,
            text="Clean Selected",
            command=self._clean_selected,
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent_hover,
            text_color="white",
            width=140,
        )
        self._clean_btn.grid(row=0, column=4, rowspan=2, padx=(0, 20), pady=20, sticky="e")

    def _build_main_area(self) -> None:
        container = ctk.CTkFrame(self, fg_color=PALETTE.bg, corner_radius=0)
        container.grid(row=1, column=1, columnspan=2, sticky="nsew")
        container.grid_columnconfigure(0, weight=3)
        container.grid_columnconfigure(1, weight=2)
        container.grid_rowconfigure(0, weight=1)

        self.scan_view = ScanView(
            container,
            on_toggle=self._on_item_toggled,
            on_select=self._on_item_selected,
        )
        self.scan_view.grid(row=0, column=0, sticky="nsew", padx=(14, 7), pady=12)

        self.detail_panel = DetailPanel(container)
        self.detail_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 14), pady=12)

        self.ports_view = PortsView(container, on_status=self._set_status)
        self.ports_view.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=14, pady=12)
        self.ports_view.grid_remove()

        from .settings_view import SettingsView

        self.settings_view = SettingsView(
            container,
            get_settings=self._get_settings,
            save_settings=self._update_settings,
        )
        self.settings_view.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=14, pady=12)
        self.settings_view.grid_remove()

    def _build_status_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=PALETTE.bg_alt)
        bar.grid(row=2, column=1, columnspan=2, sticky="nsew")
        bar.grid_columnconfigure(0, weight=1)
        self._status = ctk.CTkLabel(
            bar,
            text="Ready",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=PALETTE.text_muted,
        )
        self._status.grid(row=0, column=0, padx=14, sticky="w")

    # ------------------------------------------------------------------ state
    def _get_settings(self) -> Settings:
        return self.settings

    def _update_settings(self, new_settings: Settings) -> None:
        self.settings = new_settings
        save_settings(self.settings)
        self._set_status("Settings saved")

    def _set_status(self, text: str) -> None:
        try:
            self._status.configure(text=text)
        except Exception:
            pass

    def _on_log(self, level: str, message: str) -> None:
        self.after(0, self._set_status, message)

    # ------------------------------------------------------------------ navigation
    def _activate_nav(self, nav_id: str) -> None:
        self._active_category_id = nav_id
        for nid, btn in self._nav_buttons.items():
            if nid == nav_id:
                btn.configure(fg_color=PALETTE.bg_card)
            else:
                btn.configure(fg_color="transparent")

        if nav_id == "__ports__":
            self._show_ports()
        elif nav_id == "__settings__":
            self._show_settings()
        else:
            self._show_scan(nav_id)

    def _show_ports(self) -> None:
        self.scan_view.grid_remove()
        self.detail_panel.grid_remove()
        self.settings_view.grid_remove()
        self.ports_view.grid()
        self._title_label.configure(text="Localhost servers")
        self._subtitle_label.configure(
            text="Dev servers still listening in the background. Kill stale ones here."
        )
        self.ports_view.refresh()

    def _show_settings(self) -> None:
        self.scan_view.grid_remove()
        self.detail_panel.grid_remove()
        self.ports_view.grid_remove()
        self.settings_view.grid()
        self._title_label.configure(text="Settings")
        self._subtitle_label.configure(text="Preferences are stored in your AppData folder.")
        self.settings_view.reload()

    def _show_scan(self, category_id: str) -> None:
        self.ports_view.grid_remove()
        self.settings_view.grid_remove()
        self.scan_view.grid()
        self.detail_panel.grid()
        label = "All categories" if category_id == "all" else next(
            (c.name for c in self._categories if c.id == category_id), category_id
        )
        self._title_label.configure(text=label)
        if self._items:
            self._subtitle_label.configure(
                text=f"{len(self._visible_items())} items visible"
            )
        self._render_items()

    # ------------------------------------------------------------------ scanning
    def _auto_scan_prompt(self) -> None:
        self._set_status("Click Scan to start analysing your system")

    def _start_scan(self) -> None:
        if self._scan_thread and self._scan_thread.is_alive():
            self._set_status("Scan already running")
            return
        self._items = []
        self._checks.clear()
        self._render_items()

        self._scan_btn.configure(state="disabled", text="Scanning...")
        self._clean_btn.configure(state="disabled")
        self._quick_btn.configure(state="disabled")
        self._set_status("Scanning...")

        for cat in self._categories:
            cat.reset()

        scanner = Scanner(self._categories)
        self._scanner = scanner

        def task() -> None:
            try:
                report = scanner.run(
                    on_item=lambda item: self.after(0, self._on_scan_item, item),
                    on_progress=lambda prog: self.after(0, self._on_scan_progress, prog),
                )
                self.after(0, self._on_scan_done, report.items)
            except Exception as exc:
                _log.exception("scan failed")
                self.after(0, self._set_status, f"Scan failed: {exc}")
                self.after(0, self._finish_scan_ui)

        t = threading.Thread(target=task, daemon=True, name="scanner")
        self._scan_thread = t
        t.start()

    def _on_scan_item(self, item: CleanItem) -> None:
        if not item.detected:
            return
        if item.size_bytes <= 0 and not item.command:
            return
        self._items.append(item)
        if item.id not in self._checks:
            default = item.default_selected
            if item.risk == Risk.HIGH and not self.settings.include_high_risk_by_default:
                default = False
            self._checks[item.id] = ctk.BooleanVar(value=default)
            self._checks[item.id].trace_add("write", lambda *_: self._refresh_header())
        if self._active_category_id in ("all", item.id.split(".")[0]) or any(
            c.id == self._active_category_id and c.id == self._category_of(item)
            for c in self._categories
        ):
            self._render_items()

    def _category_of(self, item: CleanItem) -> str:
        prefix = item.id.split(".", 1)[0]
        mapping = {
            "win": "windows_system",
            "browser": "browsers",
            "dev": "dev_caches",
            "ai": "ai_caches",
            "py": "python_artifacts",
            "nodemod": "node_modules",
            "ide": "ides",
            "gaming": "gaming",
            "docker": "docker",
        }
        return mapping.get(prefix, prefix)

    def _on_scan_progress(self, progress: ScanProgress) -> None:
        self._set_status(
            f"Scanning {progress.done}/{progress.total} - {progress.current.name if progress.current else ''}"
        )

    def _on_scan_done(self, items: List[CleanItem]) -> None:
        detected = [it for it in items if it.detected and (it.size_bytes > 0 or it.command)]
        detected.sort(key=lambda i: (-i.size_bytes, RISK_ORDER[i.risk]))
        self._items = detected
        self._checks = {
            item.id: ctk.BooleanVar(
                value=(
                    item.default_selected
                    and (item.risk != Risk.HIGH or self.settings.include_high_risk_by_default)
                )
            )
            for item in self._items
        }
        for var in self._checks.values():
            var.trace_add("write", lambda *_: self._refresh_header())

        total_bytes = sum(it.size_bytes for it in detected)
        self._subtitle_label.configure(
            text=f"{len(detected)} items detected, {human_bytes(total_bytes)} total"
        )
        self._render_items()
        self._refresh_header()
        self._finish_scan_ui()
        self._set_status(
            f"Scan complete - {len(detected)} items, {human_bytes(total_bytes)} reclaimable"
        )

    def _finish_scan_ui(self) -> None:
        self._scan_btn.configure(state="normal", text="Scan")
        self._clean_btn.configure(state="normal")
        self._quick_btn.configure(state="normal")

    # ------------------------------------------------------------------ item rendering
    def _visible_items(self) -> List[CleanItem]:
        items = self._items
        if self._active_category_id != "all":
            items = [it for it in items if self._category_of(it) == self._active_category_id]
        if self._search_text:
            needle = self._search_text.lower()
            items = [
                it
                for it in items
                if needle in it.name.lower()
                or needle in it.affects.lower()
                or any(needle in str(p).lower() for p in it.paths)
            ]
        return items

    def _render_items(self) -> None:
        self.scan_view.render(
            self._visible_items(), checks=self._checks, risk_colors=RISK_COLORS
        )

    def _on_search(self, _event) -> None:
        self._search_text = self._search.get().strip()
        self._render_items()

    def _on_item_toggled(self, item_id: str) -> None:
        self._refresh_header()

    def _on_item_selected(self, item_id: str) -> None:
        found = next((it for it in self._items if it.id == item_id), None)
        self._selected_item = found
        self.detail_panel.show(found)

    def _refresh_header(self) -> None:
        selected_bytes = 0
        selected_count = 0
        for item in self._items:
            var = self._checks.get(item.id)
            if var and var.get():
                selected_bytes += max(0, item.size_bytes)
                selected_count += 1
        self._selected_label.configure(
            text=f"Selected: {selected_count} items - {human_bytes(selected_bytes)}"
        )

    # ------------------------------------------------------------------ actions
    def _quick_clean(self) -> None:
        for item in self._items:
            var = self._checks.get(item.id)
            if var is None:
                continue
            if item.risk in (Risk.SAFE, Risk.LOW) and not item.requires_admin or (
                item.requires_admin and is_admin() and item.risk in (Risk.SAFE, Risk.LOW)
            ):
                var.set(True)
            else:
                var.set(False)
        self._refresh_header()

    def _clean_selected(self) -> None:
        selected = [it for it in self._items if self._checks.get(it.id) and self._checks[it.id].get()]
        if not selected:
            messagebox.showinfo("Nothing selected", "Select at least one item to clean.")
            return

        total = sum(max(0, it.size_bytes) for it in selected)
        needs_confirm = any(it.risk in (Risk.MEDIUM, Risk.HIGH) for it in selected) or total >= (
            self.settings.confirm_threshold_mb * 1024 * 1024
        )

        admin_required = any(it.requires_admin for it in selected)
        if admin_required and not is_admin():
            if messagebox.askyesno(
                "Admin required",
                "Some of the selected items require administrative privileges.\n"
                "Relaunch as Administrator now?",
            ):
                if relaunch_as_admin():
                    self.after(250, self.destroy)
                return

        if needs_confirm:
            answer = messagebox.askyesno(
                "Confirm cleanup",
                f"About to clean {len(selected)} items totalling {human_bytes(total)}.\n"
                f"Recycle Bin: {'yes' if self.settings.use_recycle_bin else 'no'}\n"
                f"Dry-run: {'yes' if self.settings.dry_run else 'no'}\n\n"
                "Proceed?",
            )
            if not answer:
                return

        self._clean_btn.configure(state="disabled")
        self._quick_btn.configure(state="disabled")
        self._scan_btn.configure(state="disabled")

        executor = Executor(self.settings)
        dialog = ProgressDialog(self, title="Cleaning")

        def on_progress(p: CleanupProgress) -> None:
            self.after(0, dialog.update_progress, p)

        def on_result(r: CleanupResult) -> None:
            self.after(0, dialog.append_result, r)

        def restore_action_buttons() -> None:
            self._clean_btn.configure(state="normal")
            self._quick_btn.configure(state="normal")
            self._scan_btn.configure(state="normal")

        def task() -> None:
            try:
                results = executor.run(selected, on_progress=on_progress, on_result=on_result)
                total_freed = sum(r.freed_bytes for r in results)
                self.after(0, dialog.finish, results, total_freed)
                self.after(0, self._set_status, f"Freed {human_bytes(total_freed)}")
                self.after(0, lambda: self._rescan_after_clean(selected))
            except Exception as exc:
                _log.exception("cleanup failed")
                self.after(0, dialog.fail, str(exc))
            finally:
                self.after(0, restore_action_buttons)

        dialog.on_cancel = executor.abort
        t = threading.Thread(target=task, daemon=True, name="executor")
        t.start()

    def _rescan_after_clean(self, cleaned: List[CleanItem]) -> None:
        cleaned_ids = {it.id for it in cleaned}
        self._items = [it for it in self._items if it.id not in cleaned_ids]
        for iid in cleaned_ids:
            self._checks.pop(iid, None)
        self._render_items()
        self._refresh_header()

    def _elevate(self) -> None:
        if relaunch_as_admin():
            self.after(300, self.destroy)


def run() -> None:
    app = CleanerApp()
    app.mainloop()
