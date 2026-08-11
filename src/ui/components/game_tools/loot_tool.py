"""
Loot Opener — collapsible Play-tab tool.

Opens Hextech chests, capsules, orbs, and mystery boxes via LCU
using services.loot_service.LootService.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

import customtkinter as ctk

from core.constants import SPACING_MD, SPACING_SM
from services.loot_service import LootService
from ui.components.factory import get_color, get_font, make_card
from ui.components.toast import ToastManager
from ui.ui_shared import CTkTooltip
from utils.logger import Logger


class LootTool(ctk.CTkFrame):
    """Bulk-open openable loot (chests / capsules / orbs / mystery)."""

    def __init__(self, master, lcu=None, **kw):
        super().__init__(
            master,
            fg_color="transparent",
            **kw,
        )
        self.lcu = lcu
        self._busy = False
        self._stop = False
        self._rows: List[Dict[str, Any]] = []
        self._row_widgets: List[Any] = []

        self.service = LootService(lcu, log=self._on_log) if lcu else None

        self._build_ui()

    # ─────────── UI ───────────

    def _build_ui(self):
        self.card = make_card(
            self,
            title="LOOT OPENER",
            padx=0,
            pady=0,
            collapsible=True,
            start_collapsed=True,
        )

        self.lbl_count = ctk.CTkLabel(
            self.card._header,
            text="",
            font=("Inter", 9, "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            anchor="w",
            width=36,
        )
        self.lbl_count.pack(side="left", padx=(2, 0))
        self.lbl_count.configure(cursor="hand2")
        if hasattr(self.card, "_toggle_controller"):
            self.lbl_count.bind("<Button-1>", self.card._toggle_controller.toggle)

        self.body = self.card

        # Options
        opts = ctk.CTkFrame(self.body, fg_color="transparent")
        opts.pack(fill="x", padx=10, pady=(6, 2))

        self.var_keys = ctk.BooleanVar(value=True)
        self.chk_keys = ctk.CTkCheckBox(
            opts,
            text="Keys from fragments first",
            variable=self.var_keys,
            font=get_font("caption"),
            text_color=get_color("colors.text.primary"),
            fg_color=get_color("colors.accent.gold", "#C8AA6E"),
            hover_color=get_color("colors.accent.gold", "#C8AA6E"),
            checkmark_color="#0A1428",
            checkbox_width=16,
            checkbox_height=16,
        )
        self.chk_keys.pack(side="left")
        CTkTooltip(self.chk_keys, "Forge key fragments into keys before opening chests")

        self.summary_lbl = ctk.CTkLabel(
            opts,
            text="",
            font=get_font("caption"),
            text_color=get_color("colors.text.muted"),
        )
        self.summary_lbl.pack(side="right")

        # Scrollable inventory list
        self.list_frame = ctk.CTkScrollableFrame(
            self.body,
            fg_color=get_color("colors.background.card", "#0F1A24"),
            height=120,
            corner_radius=6,
        )
        self.list_frame.pack(fill="x", padx=10, pady=(4, 4))

        self.empty_lbl = ctk.CTkLabel(
            self.list_frame,
            text="Click Refresh — League Client must be logged in.",
            font=get_font("caption"),
            text_color=get_color("colors.text.muted"),
        )
        self.empty_lbl.pack(pady=16)

        # Actions
        actions = ctk.CTkFrame(self.body, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(2, 10))

        self.btn_refresh = ctk.CTkButton(
            actions,
            text="Refresh",
            width=72,
            height=28,
            font=get_font("caption", "bold"),
            fg_color=get_color("colors.background.card"),
            hover_color=get_color("colors.state.hover"),
            text_color=get_color("colors.text.primary"),
            border_width=1,
            border_color=get_color("colors.border.subtle"),
            command=self.refresh,
            cursor="hand2",
        )
        self.btn_refresh.pack(side="left")

        self.btn_open = ctk.CTkButton(
            actions,
            text="Open All",
            width=88,
            height=28,
            font=get_font("caption", "bold"),
            fg_color=get_color("colors.accent.gold", "#C8AA6E"),
            hover_color="#A88B4A",
            text_color="#0A1428",
            command=self.open_all,
            cursor="hand2",
        )
        self.btn_open.pack(side="left", padx=(6, 0))
        CTkTooltip(
            self.btn_open,
            "Open all chests, capsules, orbs & mystery boxes (never disenchants)",
        )

        self.btn_stop = ctk.CTkButton(
            actions,
            text="Stop",
            width=56,
            height=28,
            font=get_font("caption", "bold"),
            fg_color=get_color("colors.background.card"),
            hover_color="#FF4655",
            text_color=get_color("colors.text.primary"),
            border_width=1,
            border_color=get_color("colors.border.subtle"),
            command=self._request_stop,
            state="disabled",
            cursor="hand2",
        )
        self.btn_stop.pack(side="left", padx=(6, 0))

        self.status_lbl = ctk.CTkLabel(
            actions,
            text="",
            font=get_font("caption"),
            text_color=get_color("colors.text.muted"),
            anchor="e",
        )
        self.status_lbl.pack(side="right", fill="x", expand=True, padx=(8, 0))

    # ─────────── logging / status ───────────

    def _on_log(self, msg: str) -> None:
        Logger.info("Loot", msg)

        def _ui():
            if not self.winfo_exists():
                return
            short = msg if len(msg) < 48 else msg[:45] + "…"
            self.status_lbl.configure(text=short)

        try:
            self.after(0, _ui)
        except Exception:
            pass

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        try:
            self.btn_open.configure(state=state)
            self.btn_refresh.configure(state=state)
            self.btn_stop.configure(state="normal" if busy else "disabled")
        except Exception:
            pass

    def _request_stop(self) -> None:
        self._stop = True
        self._on_log("Stop requested…")

    def set_lcu(self, lcu) -> None:
        """Rebind LCU client (e.g. after late init)."""
        self.lcu = lcu
        self.service = LootService(lcu, log=self._on_log) if lcu else None

    # ─────────── list rendering ───────────

    def _clear_list(self) -> None:
        for w in self._row_widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self._row_widgets.clear()
        try:
            if self.empty_lbl.winfo_exists():
                self.empty_lbl.pack_forget()
        except Exception:
            pass

    def _render_rows(self, rows: List[Dict[str, Any]]) -> None:
        self._clear_list()
        self._rows = rows

        ready = sum(r["will_open"] for r in rows if r.get("can_open"))
        blocked = sum(1 for r in rows if r.get("needs_key") and not r.get("can_open"))
        if rows:
            self.lbl_count.configure(text=f"({ready})")
            self.summary_lbl.configure(
                text=f"{ready} ready"
                + (f" · {blocked} need key" if blocked else "")
            )
        else:
            self.lbl_count.configure(text="")
            self.summary_lbl.configure(text="")

        if not rows:
            self.empty_lbl = ctk.CTkLabel(
                self.list_frame,
                text="No openable chests / capsules / orbs found.",
                font=get_font("caption"),
                text_color=get_color("colors.text.muted"),
            )
            self.empty_lbl.pack(pady=16)
            self._row_widgets.append(self.empty_lbl)
            return

        for row in rows:
            fr = ctk.CTkFrame(self.list_frame, fg_color="transparent", height=22)
            fr.pack(fill="x", pady=1)
            fr.pack_propagate(False)

            name_color = (
                get_color("colors.text.primary")
                if row.get("can_open")
                else get_color("colors.text.muted")
            )
            will = int(row.get("will_open") or 0)
            note_bits = []
            if row.get("needs_key") and will == 0:
                note_bits.append("needs key")
            elif row.get("needs_key"):
                note_bits.append("key")
            note = f" · {note_bits[0]}" if note_bits else ""

            ctk.CTkLabel(
                fr,
                text=f"{row.get('count', 0)}×",
                width=28,
                anchor="e",
                font=get_font("caption", "bold"),
                text_color=get_color("colors.accent.gold", "#C8AA6E"),
            ).pack(side="left")
            ctk.CTkLabel(
                fr,
                text=str(row.get("name") or "?")[:28],
                anchor="w",
                font=get_font("caption"),
                text_color=name_color,
            ).pack(side="left", fill="x", expand=True, padx=(6, 0))
            ctk.CTkLabel(
                fr,
                text=(f"→{will}{note}" if will or note else "—"),
                anchor="e",
                font=get_font("caption"),
                text_color=(
                    get_color("colors.state.success", "#3FB950")
                    if will > 0
                    else get_color("colors.text.muted")
                ),
            ).pack(side="right")

            self._row_widgets.append(fr)

    # ─────────── actions ───────────

    def refresh(self) -> None:
        if self._busy:
            return
        if not self.service or not self.lcu:
            self._render_rows([])
            self.status_lbl.configure(text="No LCU client")
            return

        def work():
            rows: List[Dict[str, Any]] = []
            err = ""
            try:
                if not getattr(self.lcu, "is_connected", False):
                    if hasattr(self.lcu, "connect"):
                        self.lcu.connect(silent=True)
                if not getattr(self.lcu, "is_connected", False):
                    err = "Client not connected"
                else:
                    rows = self.service.summarize_openable()
            except Exception as e:
                err = str(e)
                Logger.error("Loot", f"Refresh failed: {e}")

            def done():
                if not self.winfo_exists():
                    return
                if err and not rows:
                    self.status_lbl.configure(text=err)
                    self._render_rows([])
                else:
                    self._render_rows(rows)
                    self.status_lbl.configure(
                        text=f"{len(rows)} stack(s)" if rows else "Empty"
                    )

            try:
                self.after(0, done)
            except Exception:
                pass

        self.status_lbl.configure(text="Scanning…")
        threading.Thread(target=work, daemon=True).start()

    def open_all(self) -> None:
        if self._busy:
            return
        if not self.service or not self.lcu:
            self.status_lbl.configure(text="No LCU client")
            return

        self._stop = False
        self._set_busy(True)
        craft_keys = bool(self.var_keys.get())

        def work():
            summary = ""
            try:
                if not getattr(self.lcu, "is_connected", False):
                    if hasattr(self.lcu, "connect"):
                        self.lcu.connect(silent=True)
                if not getattr(self.lcu, "is_connected", False):
                    summary = "Client not connected"
                else:
                    result = self.service.open_all(
                        craft_keys_first=craft_keys,
                        stop_flag=lambda: self._stop,
                    )
                    summary = (
                        f"Opened {result.opened} · failed {result.failed} · "
                        f"skipped {result.skipped} · keys {result.keys_crafted}"
                    )
            except Exception as e:
                summary = f"Error: {e}"
                Logger.error("Loot", f"Open all failed: {e}")

            def done():
                if not self.winfo_exists():
                    return
                self._set_busy(False)
                self.status_lbl.configure(text=summary)
                try:
                    ToastManager.get_instance(self.winfo_toplevel()).show(
                        summary,
                        icon="📦",
                        duration=4000,
                        theme="success" if "Opened" in summary else "error",
                    )
                except Exception:
                    pass
                self.refresh()

            try:
                self.after(0, done)
            except Exception:
                pass

        self.status_lbl.configure(text="Opening…")
        threading.Thread(target=work, daemon=True).start()
