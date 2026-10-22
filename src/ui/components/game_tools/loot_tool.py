"""
Loot Opener — Hextech visual loot inventory and opener tool.

Bulk-opens Hextech chests, capsules, orbs, and mystery boxes via LCU
using services.loot_service.LootService, featuring category visual cards,
telemetry counters, and per-stack opening capabilities.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk
from ui.components.glyphs import ctk_glyph

from services.loot_service import LootService
from ui.components.factory import get_color, get_font, make_card
from ui.components.toast import ToastManager
from ui.ui_shared import CTkTooltip
from utils.logger import Logger


def _get_loot_visuals(loot_id: str, name: str, item_type: str, category: str) -> Dict[str, str]:
    """Return styling parameters based on loot item identity."""
    lid = (loot_id or "").upper()
    nm = (name or "").upper()
    typ = (item_type or "").upper()
    cat = (category or "").upper()

    if "MASTERWORK" in lid or "MASTERWORK" in nm:
        return {
            "icon": "👑",
            "pill_text": "MASTERWORK",
            "badge_color": "#C8AA6E",
            "badge_bg": "#211A0E",
            "border_color": "#3D311A",
            "bg_color": "#0F1622",
        }
    if "CAPSULE" in lid or "CAPSULE" in nm:
        return {
            "icon": "💎",
            "pill_text": "CAPSULE",
            "badge_color": "#1ABC9C",
            "badge_bg": "#0E2922",
            "border_color": "#1B5244",
            "bg_color": "#0E1A22",
        }
    if "ORB" in lid or "ORB" in nm:
        return {
            "icon": "🔮",
            "pill_text": "ORB",
            "badge_color": "#C05CD9",
            "badge_bg": "#220F2E",
            "border_color": "#441D5E",
            "bg_color": "#121424",
        }
    if "EGG" in lid or "EGG" in nm or "LITTLE_LEGEND" in lid or "TFT" in lid:
        return {
            "icon": "🥚",
            "pill_text": "TFT EGG",
            "badge_color": "#E67E22",
            "badge_bg": "#2A180B",
            "border_color": "#522F15",
            "bg_color": "#141720",
        }
    if "BAG" in lid or "BAG" in nm or "GRAB_BAG" in lid:
        return {
            "icon": "🛍️",
            "pill_text": "GRAB BAG",
            "badge_color": "#FF6B8B",
            "badge_bg": "#2E0E1B",
            "border_color": "#5C1D36",
            "bg_color": "#141524",
        }
    if "CHEST" in lid or "CHEST" in nm or typ == "CHEST":
        return {
            "icon": "📦",
            "pill_text": "CHEST",
            "badge_color": "#0AC8B9",
            "badge_bg": "#0B1F24",
            "border_color": "#133D47",
            "bg_color": "#0D1824",
        }
    if "KEY" in lid or "KEY" in nm:
        return {
            "icon": "🗝️",
            "pill_text": "KEY",
            "badge_color": "#F1C40F",
            "badge_bg": "#29240A",
            "border_color": "#574C13",
            "bg_color": "#141820",
        }
    return {
        "icon": "🎁",
        "pill_text": "REWARD",
        "badge_color": "#5DADE2",
        "badge_bg": "#0F1F2C",
        "border_color": "#1C3C54",
        "bg_color": "#0D1622",
    }


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
            start_collapsed=False,  # Own tab — start expanded
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

        # Hextech Telemetry / Stat Chips
        self.stats_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=12, pady=(8, 2))

        # 1. Containers Chip
        self.chip_openable = ctk.CTkFrame(
            self.stats_frame,
            fg_color="#0D1520",
            border_width=1,
            border_color="#1E2B3C",
            corner_radius=6,
            width=60,
            height=46,
        )
        self.chip_openable.pack(side="left", fill="both", expand=True, padx=(0, 2))
        self.chip_openable.pack_propagate(False)

        self.lbl_stat_openable_num = ctk.CTkLabel(
            self.chip_openable,
            text="—",  # unknown until the first scan
            font=("Inter", 13, "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
        )
        self.lbl_stat_openable_num.pack(pady=(4, 0))

        self.lbl_stat_openable_sub = ctk.CTkLabel(
            self.chip_openable,
            text="Openable",
            font=("Inter", 9),
            text_color="#A0A7B4",
        )
        self.lbl_stat_openable_sub.pack(pady=(0, 4))

        # 2. Keys Chip
        self.chip_keys = ctk.CTkFrame(
            self.stats_frame,
            fg_color="#0D1520",
            border_width=1,
            border_color="#1E2B3C",
            corner_radius=6,
            width=60,
            height=46,
        )
        self.chip_keys.pack(side="left", fill="both", expand=True, padx=2)
        self.chip_keys.pack_propagate(False)

        self.lbl_stat_keys_num = ctk.CTkLabel(
            self.chip_keys,
            text="—",  # unknown until the first scan
            font=("Inter", 13, "bold"),
            text_color=get_color("colors.text.primary", "#F0E6D2"),
        )
        self.lbl_stat_keys_num.pack(pady=(4, 0))

        self.lbl_stat_keys_sub = ctk.CTkLabel(
            self.chip_keys,
            text="Keys",
            font=("Inter", 9),
            text_color="#A0A7B4",
        )
        self.lbl_stat_keys_sub.pack(pady=(0, 4))

        # 3. Fragments Chip
        self.chip_frags = ctk.CTkFrame(
            self.stats_frame,
            fg_color="#0D1520",
            border_width=1,
            border_color="#1E2B3C",
            corner_radius=6,
            width=60,
            height=46,
        )
        self.chip_frags.pack(side="left", fill="both", expand=True, padx=(2, 0))
        self.chip_frags.pack_propagate(False)

        self.lbl_stat_frags_num = ctk.CTkLabel(
            self.chip_frags,
            text="—",  # unknown until the first scan
            font=("Inter", 13, "bold"),
            text_color=get_color("colors.text.primary", "#F0E6D2"),
        )
        self.lbl_stat_frags_num.pack(pady=(4, 0))

        self.lbl_stat_frags_sub = ctk.CTkLabel(
            self.chip_frags,
            text="Fragments",
            font=("Inter", 9),
            text_color="#A0A7B4",
        )
        self.lbl_stat_frags_sub.pack(pady=(0, 4))

        # Options
        opts_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        opts_frame.pack(fill="x", padx=12, pady=(4, 1))

        self.var_claim = ctk.BooleanVar(value=True)
        self.chk_claim = ctk.CTkCheckBox(
            opts_frame,
            text="Claim rewards first",
            variable=self.var_claim,
            font=("Inter", 10),
            text_color=get_color("colors.text.primary"),
            fg_color=get_color("colors.accent.gold", "#C8AA6E"),
            hover_color=get_color("colors.accent.gold", "#C8AA6E"),
            checkmark_color="#0A1428",
            checkbox_width=15,
            checkbox_height=15,
        )
        self.chk_claim.pack(anchor="w", pady=(0, 2))
        CTkTooltip(self.chk_claim, "Claim all pending battle pass, event pass, and mission rewards before opening")

        self.var_keys = ctk.BooleanVar(value=True)
        self.chk_keys = ctk.CTkCheckBox(
            opts_frame,
            text="Craft keys first",
            variable=self.var_keys,
            font=("Inter", 10),
            text_color=get_color("colors.text.primary"),
            fg_color=get_color("colors.accent.gold", "#C8AA6E"),
            hover_color=get_color("colors.accent.gold", "#C8AA6E"),
            checkmark_color="#0A1428",
            checkbox_width=15,
            checkbox_height=15,
        )
        self.chk_keys.pack(anchor="w", pady=(1, 2))
        CTkTooltip(self.chk_keys, "Craft key fragments into keys before opening chests")

        # Resource Summary & Section Header
        self.summary_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        self.summary_frame.pack(fill="x", padx=12, pady=(4, 1))

        self.lbl_vault_header = ctk.CTkLabel(
            self.summary_frame,
            text="VAULT INVENTORY",
            font=("Inter", 9, "bold"),
            text_color=get_color("colors.text.muted", "#8A9BA8"),
            anchor="w",
        )
        self.lbl_vault_header.pack(side="left")

        self.summary_lbl = ctk.CTkLabel(
            self.summary_frame,
            text="",
            font=("Inter", 9, "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            anchor="e",
        )
        self.summary_lbl.pack(side="right")

        # Activity Progress Bar
        self.progress_bar = ctk.CTkProgressBar(
            self.body,
            height=3,
            corner_radius=2,
            fg_color="#141E28",
            # Idle bar is track-coloured: CTk draws a rounded nub even at 0,
            # which read as a stray "," under VAULT INVENTORY (#17).
            progress_color="#141E28",
        )
        self.progress_bar.pack(fill="x", padx=12, pady=(2, 2))
        self.progress_bar.set(0)

        # Bottom controls (packed side="bottom" first to guarantee space reservation)
        self.status_lbl = ctk.CTkLabel(
            self.body,
            text="",
            font=("Inter", 9),
            text_color=get_color("colors.text.muted", "#8A9BA8"),
            anchor="w",
            justify="left",
            wraplength=250,
        )
        self.status_lbl.pack(side="bottom", fill="x", padx=12, pady=(0, 4))

        self.actions_row2 = ctk.CTkFrame(self.body, fg_color="transparent")
        self.actions_row2.pack(side="bottom", fill="x", padx=12, pady=(2, 4))

        self.btn_open = ctk.CTkButton(
            self.actions_row2,
            text="Open All",
            height=28,
            corner_radius=5,
            font=("Inter", 11, "bold"),
            fg_color=get_color("colors.accent.gold", "#C8AA6E"),
            hover_color="#A88B4A",
            text_color="#0A1428",
            command=self.open_all,
            cursor="hand2",
        )
        self.btn_open.pack(side="left", fill="x", expand=True)
        CTkTooltip(
            self.btn_open,
            "Open all chests, capsules, orbs & mystery boxes (never disenchants)",
        )

        self.btn_stop = ctk.CTkButton(
            self.actions_row2,
            text="Stop",
            width=64,
            height=28,
            corner_radius=5,
            font=("Inter", 10, "bold"),
            fg_color="#2A1518",
            hover_color="#7A2D35",
            text_color="#FF6B6B",
            border_width=1,
            border_color="#5A242A",
            command=self._request_stop,
            cursor="hand2",
        )
        CTkTooltip(self.btn_stop, "Stop ongoing loot opening process")
        # btn_stop is hidden when idle to avoid permanently consuming space

        self.actions_row1 = ctk.CTkFrame(self.body, fg_color="transparent")
        self.actions_row1.pack(side="bottom", fill="x", padx=12, pady=(4, 2))

        self.btn_refresh = ctk.CTkButton(
            self.actions_row1,
            text="Refresh",
            height=28,
            corner_radius=5,
            font=("Inter", 10, "bold"),
            fg_color=get_color("colors.background.card", "#101923"),
            hover_color=get_color("colors.state.hover", "#1B2A3B"),
            text_color=get_color("colors.text.primary", "#F0F6FC"),
            border_width=1,
            border_color=get_color("colors.border.subtle", "#1E2B3C"),
            command=self.refresh,
            cursor="hand2",
        )
        self.btn_refresh.pack(side="left", fill="x", expand=True, padx=(0, 4))
        CTkTooltip(self.btn_refresh, "Refresh inventory from League Client")

        self.btn_claim = ctk.CTkButton(
            self.actions_row1,
            text="Claim",
            height=28,
            corner_radius=5,
            font=("Inter", 10, "bold"),
            fg_color=get_color("colors.background.card", "#101923"),
            hover_color=get_color("colors.state.hover", "#1B2A3B"),
            text_color=get_color("colors.text.primary", "#F0F6FC"),
            border_width=1,
            border_color=get_color("colors.border.subtle", "#1E2B3C"),
            command=self.claim_rewards,
            cursor="hand2",
        )
        self.btn_claim.pack(side="left", fill="x", expand=True, padx=(4, 0))
        CTkTooltip(self.btn_claim, "Claim pending battle pass, event pass, and mission rewards")

        # Scrollable inventory list
        self.list_frame = ctk.CTkScrollableFrame(
            self.body,
            fg_color=get_color("colors.background.card", "#0F1A24"),
            height=125,
            corner_radius=6,
        )
        self.list_frame.pack(fill="both", expand=True, padx=12, pady=(2, 4))

        self.empty_lbl = ctk.CTkLabel(
            self.list_frame,
            text="Open League, then Refresh to scan your chests and capsules.",
            font=get_font("caption"),
            text_color="#A0A7B4",
            wraplength=220,
        )
        self.empty_lbl.pack(pady=16)

    # ─────────── logging / status ───────────

    def _on_log(self, msg: str) -> None:
        Logger.info("Loot", msg)

        def _ui():
            if not self.winfo_exists():
                return
            short = msg if len(msg) < 52 else msg[:49] + "…"
            self.status_lbl.configure(text=short)

        try:
            self.after(0, _ui)
        except Exception as exc:
            Logger.debug("LootTool", "_on_log suppressed an error", exc=exc)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        try:
            self.btn_open.configure(state=state)
            self.btn_claim.configure(state=state)
            self.btn_refresh.configure(state=state)
            if busy:
                if hasattr(self, "btn_stop") and not self.btn_stop.winfo_ismapped():
                    self.btn_stop.pack(side="right", padx=(8, 0))
                self.btn_stop.configure(state="normal")
                self.progress_bar.configure(mode="indeterminate",
                                            progress_color=get_color("colors.accent.gold", "#C8AA6E"))
                self.progress_bar.start()
            else:
                if hasattr(self, "btn_stop") and self.btn_stop.winfo_ismapped():
                    self.btn_stop.pack_forget()
                self.btn_stop.configure(state="disabled")
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
                self.progress_bar.set(0)
                self.progress_bar.configure(progress_color="#141E28")
        except Exception as exc:
            Logger.debug("LootTool", "_set_busy suppressed an error", exc=exc)

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
            except Exception as exc:
                Logger.debug("LootTool", "_clear_list suppressed an error", exc=exc)
        self._row_widgets.clear()
        try:
            if hasattr(self, "empty_lbl") and self.empty_lbl.winfo_exists():
                self.empty_lbl.pack_forget()
        except Exception as exc:
            Logger.debug("LootTool", "_clear_list suppressed an error", exc=exc)

    def _render_empty_state(self, message: str = "No openable containers found.",
                            title: str = "Nothing to open", offline: bool = False,
                            error: bool = False) -> None:
        if hasattr(self, "list_frame") and self.list_frame.winfo_exists():
            self.list_frame.configure(height=125)

        empty_box = ctk.CTkFrame(
            self.list_frame,
            fg_color="#0B131C",
            border_width=1,
            border_color="#182330",
            corner_radius=8,
        )
        empty_box.pack(fill="x", padx=8, pady=20)

        # Hextech graphic icon
        from ui.components.glyphs import ctk_glyph
        ctk.CTkLabel(
            empty_box,
            text="",
            image=(ctk_glyph("warning", "#E0A43A", 26) if error
                   else ctk_glyph("chest", "#5B6573" if offline else "#C8AA6E", 26)),
        ).pack(pady=(12, 4))

        ctk.CTkLabel(
            empty_box,
            text=title,
            font=("Inter", 12, "bold"),
            text_color=get_color("colors.text.primary", "#F0F6FC"),
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            empty_box,
            text=message,
            font=("Inter", 9),
            text_color="#A0A7B4",
            wraplength=220,
            justify="center",
        ).pack(pady=(0, 12), padx=12)

        btn_scan = ctk.CTkButton(
            empty_box,
            text="Scan again",
            font=("Inter", 10, "bold"),
            width=120,
            height=24,
            corner_radius=5,
            fg_color="#162534",
            hover_color="#1F344A",
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            command=self.refresh,
            cursor="hand2",
        )
        if error:
            btn_scan.configure(text="Retry")
        if offline:
            btn_scan.configure(state="disabled", text="Waiting for client",
                               text_color_disabled="#8A93A0")
        btn_scan.pack(pady=(0, 12))

        self._row_widgets.append(empty_box)

    def _show_offline(self) -> None:
        """Honest offline state: no fake zeros, and actions that need the
        client are disabled instead of failing on click."""
        self._clear_list()
        self._rows = []
        for lbl in (self.lbl_stat_openable_num, self.lbl_stat_keys_num, self.lbl_stat_frags_num):
            lbl.configure(text="—")
        self.lbl_count.configure(text="")
        self.summary_lbl.configure(text="")
        self._render_empty_state(
            "Loot shows up here once League is running.",
            title="No client connected", offline=True,
        )
        self.btn_open.configure(state="disabled", fg_color="#1A2430", text_color_disabled="#8A93A0")
        self.btn_claim.configure(state="disabled", text_color_disabled="#8A93A0")
        self.status_lbl.configure(text="")

    def _show_error(self, err: str) -> None:
        """Inline error + Retry row (#29) instead of an empty list and a log line."""
        self._clear_list()
        self._rows = []
        detail = str(err).strip() or "Unknown error"
        if len(detail) > 90:
            detail = detail[:89] + "…"
        self._render_empty_state(
            f"{detail}\nCheck that League is open, then retry.",
            title="Couldn't read your loot", error=True,
        )
        self.status_lbl.configure(text="")

    def _render_rows(self, rows: List[Dict[str, Any]], keys: int = 0, frags: int = 0) -> None:
        self._clear_list()
        if not self._busy:
            self.btn_open.configure(state="normal", fg_color=get_color("colors.accent.gold", "#C8AA6E"))
            self.btn_claim.configure(state="normal")
        self._rows = rows

        ready = sum(r["will_open"] for r in rows if r.get("can_open"))
        blocked = sum(1 for r in rows if r.get("needs_key") and not r.get("can_open"))

        # Update telemetry labels
        self.lbl_stat_openable_num.configure(text=str(ready))
        self.lbl_stat_keys_num.configure(text=str(keys))
        craftable_keys = frags // 3
        frags_sub = f"Fragments (+{craftable_keys} key{'s' if craftable_keys != 1 else ''})" if craftable_keys > 0 else "Fragments"
        self.lbl_stat_frags_sub.configure(text=frags_sub)
        self.lbl_stat_frags_num.configure(text=str(frags))

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
            self._render_empty_state("No openable chests, capsules, or orbs found.")
            return

        # Responsive inventory height: adapts to row count within bounds
        calc_h = max(60, min(170, len(rows) * 52 + 6))
        if hasattr(self, "list_frame") and self.list_frame.winfo_exists():
            self.list_frame.configure(height=calc_h)

        for idx, row in enumerate(rows):
            loot_id = str(row.get("loot_id") or "")
            name = str(row.get("name") or "Loot Item")
            count = int(row.get("count") or 0)
            item_type = str(row.get("type") or "")
            cat = str(row.get("category") or "")
            can_open = bool(row.get("can_open"))
            needs_key = bool(row.get("needs_key"))
            will = int(row.get("will_open") or 0)

            visuals = _get_loot_visuals(loot_id, name, item_type, cat)

            # Single-accent rows (#20): neutral card, gold only marks what
            # can be opened now; drawn chest glyph instead of emoji badges.
            card_fr = ctk.CTkFrame(
                self.list_frame,
                fg_color=get_color("colors.background.card", "#0F1923"),
                border_width=1,
                border_color="#6E5C3A" if can_open else "#2A3442",
                corner_radius=6,
                height=48,
            )
            pad_bottom = 6 if idx == len(rows) - 1 else 2
            card_fr.pack(fill="x", pady=(2, pad_bottom), padx=(4, 8))
            card_fr.pack_propagate(False)

            icon_badge = ctk.CTkLabel(
                card_fr, text="", width=34, height=34,
                fg_color="#141E28", corner_radius=5,
                image=ctk_glyph("chest", "#C8AA6E" if can_open else "#8A93A0", 20),
            )
            icon_badge.pack(side="left", padx=(4, 4), pady=8)

            # Right column is packed before the info column so a long name
            # can't squeeze the per-row Open button out of the card.
            action_col = ctk.CTkFrame(card_fr, fg_color="transparent")
            action_col.pack(side="right", padx=(4, 8), pady=8)

            # Center: Info Column (Name & Status)
            info_col = ctk.CTkFrame(card_fr, fg_color="transparent")
            info_col.pack(side="left", fill="both", expand=True, pady=4)

            # Row 1: Quantity + Name
            top_row = ctk.CTkFrame(info_col, fg_color="transparent", height=18)
            top_row.pack(fill="x")
            top_row.pack_propagate(False)

            ctk.CTkLabel(
                top_row,
                text=f"{count}×",
                font=("Inter", 11, "bold"),
                text_color=get_color("colors.accent.gold", "#C8AA6E"),
            ).pack(side="left")

            display_name = name if len(name) <= 13 else name[:12].rstrip() + "…"
            name_lbl = ctk.CTkLabel(
                top_row,
                text=display_name,
                font=("Inter", 11, "bold"),
                text_color=get_color("colors.text.primary", "#F0F6FC") if can_open else get_color("colors.text.muted", "#8A9BA8"),
                anchor="w",
            )
            name_lbl.pack(side="left", padx=(4, 0), fill="x", expand=True)
            if len(name) > 13:
                CTkTooltip(name_lbl, name)

            # Row 2: Category Pill + Status Pill
            bot_row = ctk.CTkFrame(info_col, fg_color="transparent", height=16)
            bot_row.pack(fill="x")
            bot_row.pack_propagate(False)

            ctk.CTkLabel(
                bot_row,
                text=str(visuals['pill_text']).title(),
                font=("Inter", 8, "bold"),
                text_color="#A0A7B4",
            ).pack(side="left")

            if can_open:
                status_text = f"Ready ({will})" if will > 1 else "Ready"
                status_color = "#2ECC71"
            elif needs_key:
                status_text = "Needs key"
                status_color = "#E0A43A"
            else:
                status_text = "Blocked"
                status_color = "#8A93A0"

            ctk.CTkLabel(
                bot_row,
                text=f" · {status_text}",
                font=("Inter", 8),
                text_color=status_color,
            ).pack(side="left", padx=(2, 0))


            if can_open:
                btn_single = ctk.CTkButton(
                    action_col,
                    text="Open",
                    width=46,
                    height=24,
                    corner_radius=4,
                    font=("Inter", 10, "bold"),
                    fg_color=get_color("colors.accent.gold", "#C8AA6E"),
                    hover_color="#A88B4A",
                    text_color="#0A1428",
                    command=lambda lid=loot_id: self.open_single(lid),
                    cursor="hand2",
                )
                btn_single.pack()
                CTkTooltip(btn_single, f"Open stack of {name}")
            elif needs_key:
                need_badge = ctk.CTkFrame(
                    action_col,
                    width=52,
                    height=22,
                    fg_color="#18202A",
                    border_width=1,
                    border_color="#2A374A",
                    corner_radius=4,
                )
                need_badge.pack()
                need_badge.pack_propagate(False)
                ctk.CTkLabel(
                    need_badge,
                    text="Need Key",
                    font=("Inter", 8),
                    text_color="#8A9BA8",
                ).pack(expand=True)

            self._row_widgets.append(card_fr)

    # ─────────── actions ───────────

    def claim_rewards(self) -> None:
        """Claim all pending pass, mission, and milestone rewards."""
        if self._busy:
            return
        if not self.service or not self.lcu:
            self.status_lbl.configure(text="League client isn't running")
            return

        self._set_busy(True)
        self.status_lbl.configure(text="Claiming rewards…")

        def work():
            msg = ""
            try:
                if not getattr(self.lcu, "is_connected", False):
                    if hasattr(self.lcu, "connect"):
                        self.lcu.connect(silent=True)
                if not getattr(self.lcu, "is_connected", False):
                    msg = "Client not connected"
                else:
                    res = self.service.claim_all_rewards()
                    if res.claimed > 0:
                        msg = f"Claimed {res.claimed} reward{'s' if res.claimed != 1 else ''}"
                    else:
                        msg = "No rewards pending"
            except Exception as e:
                msg = f"Claim error: {e}"
                Logger.error("Loot", f"Claim rewards failed: {e}")

            def done():
                if not self.winfo_exists():
                    return
                self._set_busy(False)
                self.status_lbl.configure(text=msg)
                try:
                    ToastManager.get_instance(self.winfo_toplevel()).show(
                        msg,
                        icon="🎁",
                        duration=3500,
                        theme="success" if "Claimed" in msg else "neutral",
                    )
                except Exception as exc:
                    Logger.debug("LootTool", "done suppressed an error", exc=exc)
                self.refresh()

            try:
                self.after(0, done)
            except Exception as exc:
                Logger.debug("LootTool", "work suppressed an error", exc=exc)

        threading.Thread(target=work, daemon=True).start()

    def refresh(self) -> None:
        if self._busy:
            return
        if not self.service or not self.lcu or getattr(self.lcu, "is_connected", True) is False:
            self._show_offline()
            return

        def work():
            rows: List[Dict[str, Any]] = []
            keys = 0
            frags = 0
            err = ""
            try:
                if not getattr(self.lcu, "is_connected", False):
                    if hasattr(self.lcu, "connect"):
                        self.lcu.connect(silent=True)
                if not getattr(self.lcu, "is_connected", False):
                    err = "Client not connected"
                else:
                    loot_items = self.service.fetch_loot()
                    rows = self.service.summarize_openable(items=loot_items)
                    keys = self.service.count_keys(items=loot_items)
                    frags = self.service.count_key_fragments(items=loot_items)
            except Exception as e:
                err = str(e)
                Logger.error("Loot", f"Refresh failed: {e}")

            def done():
                if not self.winfo_exists():
                    return
                if err and not rows:
                    self._show_error(err)
                else:
                    self._render_rows(rows, keys, frags)
                    self.status_lbl.configure(
                        text=f"{len(rows)} stack(s) detected" if rows else "Ready"
                    )

            try:
                self.after(0, done)
            except Exception as exc:
                Logger.debug("LootTool", "work suppressed an error", exc=exc)

        self.status_lbl.configure(text="Scanning…")
        threading.Thread(target=work, daemon=True).start()

    def open_single(self, loot_id: str) -> None:
        """Open a single specific loot stack."""
        if self._busy:
            return
        if not self.service or not self.lcu:
            self.status_lbl.configure(text="League client isn't running")
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
                    res = self.service.open_all(
                        craft_keys_first=craft_keys,
                        max_passes=2,
                        only_ids={loot_id},
                        stop_flag=lambda: self._stop,
                        claim_rewards_first=False,
                    )
                    summary = f"Opened {res.opened} · failed {res.failed} · skipped {res.skipped}"
            except Exception as e:
                summary = f"Error: {e}"
                Logger.error("Loot", f"Open single item failed: {e}")

            def done():
                if not self.winfo_exists():
                    return
                self._set_busy(False)
                self.status_lbl.configure(text=summary)
                try:
                    ToastManager.get_instance(self.winfo_toplevel()).show(
                        summary,
                        icon="📦",
                        duration=3500,
                        theme="success" if "Opened 0" not in summary and "Opened" in summary else "neutral",
                    )
                except Exception as exc:
                    Logger.debug("LootTool", "done suppressed an error", exc=exc)
                self.refresh()

            try:
                self.after(0, done)
            except Exception as exc:
                Logger.debug("LootTool", "work suppressed an error", exc=exc)

        self.status_lbl.configure(text="Opening stack…")
        threading.Thread(target=work, daemon=True).start()

    def open_all(self) -> None:
        if self._busy:
            return
        if not self.service or not self.lcu:
            self.status_lbl.configure(text="League client isn't running")
            return

        self._stop = False
        self._set_busy(True)
        craft_keys = bool(self.var_keys.get())
        claim_rewards = bool(self.var_claim.get())

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
                        claim_rewards_first=claim_rewards,
                        stop_flag=lambda: self._stop,
                    )
                    claimed_str = f"claimed {result.rewards_claimed} · " if result.rewards_claimed else ""
                    summary = (
                        f"{claimed_str}Opened {result.opened} · failed {result.failed} · "
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
                        theme="success" if "Opened" in summary and "Opened 0" not in summary else "neutral",
                    )
                except Exception as exc:
                    Logger.debug("LootTool", "done suppressed an error", exc=exc)
                self.refresh()

            try:
                self.after(0, done)
            except Exception as exc:
                Logger.debug("LootTool", "work suppressed an error", exc=exc)

        self.status_lbl.configure(text="Opening…")
        threading.Thread(target=work, daemon=True).start()
