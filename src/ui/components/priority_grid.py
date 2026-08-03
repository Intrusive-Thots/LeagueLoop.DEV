"""
Priority Icon Grid — Collapsible, scrollable champion icon grid.
Reorder via select + ▲▼⤒ buttons (no drag-and-drop).
Icons loaded from cache/assets/champion_{Name}.png.
"""
import math
import os
import tkinter as tk
import customtkinter as ctk

from utils.path_utils import get_asset_path
from ui.components.factory import get_color, get_font, get_radius, make_input
from ui.ui_shared import CTkTooltip
from ui.components.toast import ToastManager
from core.constants import SPACING_SM, SPACING_MD
from utils.smooth_scroll import apply_smooth_scroll

ICON_SIZE = 40
ICONS_PER_ROW = 4
GRID_GAP = SPACING_SM

# Selection colours
SEL_BORDER = get_color("colors.accent.gold", "#C8AA6E")  # gold ring for single-select in edit mode
SEL_BG     = get_color("colors.background.card", "#141E28")  # dark blue tint
DEL_BORDER = get_color("colors.state.danger", "#E74C3C")    # red for delete-marked
DEL_BG     = get_color("colors.state.danger.muted", "#4d1111")

_CLEAN_TRANS = str.maketrans("", "", " '.")

CHAMPION_ALIASES = {
    "tf": "Twisted Fate", "mf": "Miss Fortune", "ww": "Warwick", "j4": "Jarvan IV",
    "asol": "Aurelion Sol", "yi": "Master Yi", "kog": "Kog'Maw", "noc": "Nocturne",
    "heimer": "Heimerdinger", "cass": "Cassiopeia", "kat": "Katarina", "trist": "Tristana",
    "blitz": "Blitzcrank", "cho": "Cho'Gath", "mundo": "Dr. Mundo", "eve": "Evelynn",
    "gp": "Gangplank", "heka": "Hecarim", "ksante": "K'Sante", "lb": "LeBlanc",
    "lee": "Lee Sin", "liss": "Lissandra", "malz": "Malzahar", "morg": "Morgana",
    "naut": "Nautilus", "panth": "Pantheon", "pant": "Pantheon", "reksai": "Rek'Sai",
    "rene": "Renekton", "renek": "Renekton", "sej": "Sejuani", "tahm": "Tahm Kench",
    "kench": "Tahm Kench", "trynd": "Tryndamere", "vel": "Vel'Koz", "vlad": "Vladimir",
    "voli": "Volibear", "xin": "Xin Zhao", "zil": "Zilean", "fiddle": "Fiddlesticks",
    "fiddles": "Fiddlesticks"
}


class PriorityIconGrid(ctk.CTkFrame):
    """Icon grid with collapse, add, edit (select → ▲▼⤒ reorder + multi-delete)."""

    def __init__(self, master, config, assets, expanded: bool = False, **kw):
        super().__init__(master, fg_color=get_color("colors.background.panel", "#0F1A24"), corner_radius=8, **kw)
        self.config = config
        self.assets = assets

        self._expanded = expanded
        self._edit_mode = False
        self._selected_indices = set()   # set of selected indices for reorder/mass-delete
        self._delete_marked = set()      # indices marked for deletion
        self._icon_widgets = []
        self._undo_stack = []            # stack of previous priority lists for undo
        self._tip = None                 # Item #133: Initialize tooltip ref in __init__
        self._debounce_timer = None      # Item #23: Initialize debounce timer in __init__
        self._hovered_champ_name = None  # Currently hovered champion for hover preview
        self._clear_confirm = False      # Whether clear-all is in confirmation mode
        self._shake_phase = 0            # Edit-mode shake animation phase counter
        self._parsed_import = None       # Cached parsed import data
        self._drag_data = {"widget": None, "start_x": 0, "start_y": 0, "idx": -1, "ghost": None, "cell": None}
        self._icons_per_row = ICONS_PER_ROW

        self._build_header()
        self._build_body()
        self._known_champions = self._scan_known_champions()
        self._render_grid()

    def set_icons_per_row(self, count: int):
        """Dynamically set columns per row and re-render grid layout."""
        count = max(1, count)
        if getattr(self, "_icons_per_row", ICONS_PER_ROW) != count:
            self._icons_per_row = count
            self._render_grid()

    # ───────────── helpers ─────────────
    def _scan_known_champions(self):
        from utils.path_utils import get_data_dir
        
        known = {}
        dirs_to_check = [
            get_asset_path("assets"),
            os.path.join(get_data_dir(), "cache", "assets")
        ]
        
        for d in dirs_to_check:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.startswith("champion_") and f.endswith(".png"):
                        real = f[len("champion_"):-len(".png")]
                        known[real.lower()] = real

        # ⚡ Bolt: Precompute and sort normalized names to eliminate .lower() and sorted()
        # allocations from the hot-path _on_add_typing loop
        self._search_cache = sorted([(v.lower(), v) for v in known.values()], key=lambda x: x[1])
        return known

    def _resolve_champion_name(self, raw):
        if not raw:
            return None
        raw_clean = raw.strip()
        alias_target = CHAMPION_ALIASES.get(raw_clean.lower())
        if alias_target:
            res = self._known_champions.get(alias_target.lower())
            if res:
                return res

        res = self._known_champions.get(raw_clean)
        if res:
            return res

        normalized = raw_clean.translate(_CLEAN_TRANS).lower()
        return self._known_champions.get(normalized)

    @staticmethod
    def _dedup(seq):
        """Remove duplicates while preserving order."""
        return list(dict.fromkeys(seq))

    def _get_priority_list(self):
        raw = self.config.get("priority_picker", {}).get("list", [])
        return self._dedup(raw)

    def _save_priority_list(self, lst, record_history=True):
        if record_history:
            current = self._get_priority_list()
            # Only push if it actually changed
            if current != lst:
                self._undo_stack.append(current)
                # Cap the stack at, say, 10 items
                if len(self._undo_stack) > 10:
                    self._undo_stack.pop(0)

        cfg = self.config.get("priority_picker", {})
        cfg["list"] = self._dedup(lst)
        self.config.set("priority_picker", cfg)

        if hasattr(self, "_sync_undo_btn"):
            self._sync_undo_btn()

    def _sync_undo_btn(self):
        if not hasattr(self, "btn_undo"):
            return
        if self._undo_stack:
            self.btn_undo.configure(state="normal", text_color=get_color("colors.text.primary"))
        else:
            self.btn_undo.configure(state="disabled", text_color=get_color("colors.text.disabled"))

    # ───────────── header ─────────────
    def _build_header(self):
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=24)
        self.header.pack(fill="x", padx=SPACING_MD, pady=(SPACING_MD, 0))

        self.lbl_section = ctk.CTkLabel(
            self.header, text="▶  ARAM LIST",
            font=get_font("caption", "bold"),
            text_color=get_color("colors.text.muted"), anchor="w",
            cursor="hand2"
        )
        self.lbl_section.pack(side="left", padx=2)
        CTkTooltip(self.lbl_section, "Toggle ARAM List")
        self.lbl_section.bind("<Button-1>", lambda e: self._toggle_collapse())
        self.lbl_section.bind("<Enter>", lambda e: self.lbl_section.configure(text_color=get_color("colors.text.primary")))
        self.lbl_section.bind("<Leave>", lambda e: self.lbl_section.configure(text_color=get_color("colors.text.muted")))

        # Item #141: Count badge
        self.lbl_count = ctk.CTkLabel(
            self.header, text="0", width=22, height=18,
            corner_radius=9, fg_color=get_color("colors.accent.primary"),
            text_color=get_color("colors.background.app"),
            font=get_font("caption", "bold")
        )
        self.lbl_count.pack(side="left", padx=(4, 0))

        # Edit / Done
        self.btn_edit = ctk.CTkButton(
            self.header, text="Edit", width=40, height=20,
            corner_radius=get_radius("sm"), font=get_font("caption"),
            fg_color="transparent",
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            hover_color=get_color("colors.state.hover"),
            command=self._toggle_edit_mode, cursor="hand2",
            )
        self.btn_edit.pack(side="right", padx=2)
        CTkTooltip(self.btn_edit, "Toggle Edit Mode")

        # +
        self.btn_add = ctk.CTkButton(
            self.header, text="+", width=20, height=20,
            corner_radius=10, font=get_font("body", "bold"),
            fg_color="transparent",
            text_color=get_color("colors.accent.primary"),
            hover_color=get_color("colors.state.hover"),
            command=self._show_add_input, cursor="hand2",
            )
        self.btn_add.pack(side="right")
        CTkTooltip(self.btn_add, "Add Champion")

        # Undo
        self.btn_undo = ctk.CTkButton(
            self.header, text="↶", width=20, height=20,
            corner_radius=10, font=get_font("body"),
            fg_color="transparent",
            text_color=get_color("colors.text.disabled"),
            hover_color=get_color("colors.state.hover"),
            command=self._undo_action,
            state="disabled", cursor="hand2",
            )
        self.btn_undo.pack(side="right", padx=2)
        CTkTooltip(self.btn_undo, "Undo Last Action")

        # Import
        self.btn_import = ctk.CTkButton(
            self.header, text="⎗", width=20, height=20,
            corner_radius=10, font=get_font("body"),
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover"),
            command=self._show_import_preview, cursor="hand2",
            )
        self.btn_import.pack(side="right", padx=2)
        CTkTooltip(self.btn_import, "Import ARAM List from Clipboard")

        # Export
        self.btn_export = ctk.CTkButton(
            self.header, text="⎘", width=20, height=20,
            corner_radius=10, font=get_font("body"),
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover"),
            command=self._export_list, cursor="hand2",
            )
        self.btn_export.pack(side="right")
        CTkTooltip(self.btn_export, "Export ARAM List to Clipboard")

    # ───────────── body ─────────────
    def _build_body(self):
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        if self._expanded:
            self.body.pack(fill="both", expand=True, pady=(SPACING_SM, SPACING_MD), padx=SPACING_MD)

        # ── Hovered Champion Display ──
        self.hover_frame = ctk.CTkFrame(self.body, fg_color="#141E28", corner_radius=get_radius("sm"), height=48)
        self.hover_frame.pack_propagate(False)

        self.hover_icon = ctk.CTkLabel(self.hover_frame, text="", width=32, height=32, fg_color="transparent")
        self.hover_icon.pack(side="left", padx=(8, 12), pady=8)

        self.hover_name = ctk.CTkLabel(self.hover_frame, text="None", font=get_font("body", "bold"), text_color=get_color("colors.text.primary"))
        self.hover_name.pack(side="left")

        self.hover_add_btn = ctk.CTkButton(
            self.hover_frame, text="+ Add", width=60, height=28,
            corner_radius=get_radius("sm"), font=get_font("caption", "bold"),
            fg_color=get_color("colors.accent.primary"),
            hover_color=get_color("colors.state.hover"),
            command=self._add_hovered_champion, cursor="hand2",
            )
        self.hover_add_btn.pack(side="right", padx=(8, 8))
        self._hovered_champ_name = None

        self.scroll = ctk.CTkScrollableFrame(
            self.body, fg_color="transparent", height=220,
            scrollbar_button_color=get_color("colors.text.disabled"),
            scrollbar_button_hover_color=get_color("colors.text.muted"),
            scrollbar_fg_color="transparent",
        )
        # Slim the scrollbar track so it doesn't eat into champion icons
        try:
            self.scroll._scrollbar.configure(width=6)
        except Exception:
            pass
        self.scroll.pack(fill="both", expand=True, pady=(0, SPACING_SM))
        apply_smooth_scroll(self.scroll)

        # Grid container enforcing 4 columns
        self.grid_parent = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.grid_parent.pack(pady=(0, SPACING_MD))
        
        # Let the frame dynamically resize its height based on children
        self.grid_parent.configure(width=200)

        for i in range(ICONS_PER_ROW):
            self.grid_parent.grid_columnconfigure(i, weight=0, minsize=48)

        # Add-champion input row (Always visible & accessible)
        self.add_container = ctk.CTkFrame(self.body, fg_color="#141E28", corner_radius=get_radius("sm"))
        self.add_container.pack(fill="x", pady=(0, SPACING_SM))

        self.add_row = ctk.CTkFrame(self.add_container, fg_color="transparent", height=32)
        self.add_row.pack(fill="x", padx=8, pady=4)

        self.add_entry = make_input(
            self.add_row,
            placeholder="Search or add champion by name...",
            width=160,
            height=28,
            font=get_font("caption")
        )
        self.add_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.add_entry.bind("<Return>", lambda e: self._commit_add())
        self.add_entry.bind("<KeyRelease>", self._on_add_typing)

        ctk.CTkButton(
            self.add_row, text="+ Add", width=52, height=28,
            corner_radius=get_radius("sm"), font=get_font("caption", "bold"),
            fg_color=get_color("colors.accent.primary"),
            hover_color=get_color("colors.state.hover"),
            command=self._commit_add, cursor="hand2",
        ).pack(side="left")

        # Suggestions frame (hidden initially)
        self.suggestions_frame = ctk.CTkFrame(self.add_container, fg_color="transparent")

        # Import container (hidden initially)
        self.import_container = ctk.CTkFrame(self.body, fg_color="transparent")

        self.import_header = ctk.CTkFrame(self.import_container, fg_color="transparent", height=28)
        self.import_header.pack(fill="x", pady=(0, 4))

        self.lbl_import_preview = ctk.CTkLabel(
            self.import_header, text="Preview Import",
            font=get_font("caption", "bold"),
            text_color=get_color("colors.accent.primary")
        )
        self.lbl_import_preview.pack(side="left", padx=(4, 0))

        ctk.CTkButton(
            self.import_header, text="✕", width=24, height=24,
            corner_radius=get_radius("sm"), font=get_font("body"),
            fg_color="transparent", hover_color=get_color("colors.state.danger", "#e81123"),
            text_color=get_color("colors.text.muted"),
            command=self._close_import, cursor="hand2",
            ).pack(side="right")

        self.btn_import_apply = ctk.CTkButton(
            self.import_header, text="✓ Apply", width=60, height=24,
            corner_radius=get_radius("sm"), font=get_font("caption", "bold"),
            fg_color=get_color("colors.state.success"),
            hover_color="#00b359",
            text_color="#ffffff",
            command=self._commit_import, cursor="hand2",
            )
        self.btn_import_apply.pack(side="right", padx=(0, 4))

        self.import_scroll = ctk.CTkScrollableFrame(
            self.import_container, height=60, fg_color="transparent",
            orientation="horizontal",
            scrollbar_button_color=get_color("colors.text.disabled"),
            scrollbar_button_hover_color=get_color("colors.text.muted")
        )
        self.import_scroll.pack(fill="x", padx=4)

        # ── Edit-mode control bar (hidden until edit) ──
        self.edit_bar = ctk.CTkFrame(self.body, fg_color="transparent", height=30)

        # In Drag-and-Drop mode, we only need the mass-delete controls
        self.lbl_edit_hint = ctk.CTkLabel(
            self.edit_bar, text="Drag to reorder. Click to select for deletion.",
            font=get_font("caption", "italic"), text_color=get_color("colors.text.disabled")
        )
        self.lbl_edit_hint.pack(side="left", padx=4)

        self.btn_del = ctk.CTkButton(
            self.edit_bar, text="✕ Delete Selected", height=24,
            corner_radius=get_radius("sm"), font=get_font("body", "bold"),
            fg_color="transparent", hover_color=get_color("colors.state.danger.muted", "#4d1111"),
            text_color=get_color("colors.state.danger", "#ff4444"), command=self._delete_active, cursor="hand2",
            )

        self.btn_clear_all = ctk.CTkButton(
            self.edit_bar, text="🗑️ Clear All", height=24,
            corner_radius=get_radius("sm"), font=get_font("body"),
            fg_color="transparent", hover_color=get_color("colors.state.danger.muted", "#4d1111"),
            text_color=get_color("colors.state.danger", "#ff4444"), command=self._request_clear_all, cursor="hand2",
            )

        self.btn_clear_all.pack(side="right", padx=1)
        CTkTooltip(self.btn_clear_all, "Clear All")
        self.btn_del.pack(side="right", padx=1)
        CTkTooltip(self.btn_del, "Remove")

    # ───────────── hovered champion integration ─────────────
    def set_hovered_champion(self, champ_id):
        if not champ_id:
            if hasattr(self, "hover_frame") and self.hover_frame.winfo_viewable():
                self.hover_frame.pack_forget()
            self._hovered_champ_name = None
            return

        champ_name = self.assets.get_champ_name(champ_id)
        if not champ_name:
            if hasattr(self, "hover_frame") and self.hover_frame.winfo_viewable():
                self.hover_frame.pack_forget()
            self._hovered_champ_name = None
            return

        self._hovered_champ_name = champ_name
        self.hover_name.configure(text=champ_name)
        
        # Check if already in priority list
        plist = self._get_priority_list()
        # ⚡ Bolt: Optimize O(N) list traversal by hoisting the target string allocation
        # outside the loop and using a short-circuiting generator expression.
        champ_lower = champ_name.lower()
        in_list = any(p.lower() == champ_lower for p in plist)
                
        if in_list:
            self.hover_add_btn.configure(state="disabled", text="Added", fg_color="transparent", text_color=get_color("colors.text.disabled"))
        else:
            self.hover_add_btn.configure(state="normal", text="+ Add", fg_color=get_color("colors.accent.primary"), text_color="#ffffff")

        # Load icon
        def _update_hover_icon(img):
            if hasattr(self, "hover_icon") and self.hover_icon.winfo_exists():
                self.hover_icon.configure(image=img, text="", fg_color="transparent")

        self.assets.get_icon_async("champion", champ_name, _update_hover_icon, size=(ICON_SIZE, ICON_SIZE), widget=self.hover_icon)
            
        if not self.hover_frame.winfo_viewable():
            # Show it above the scroll area (only if body is visible)
            try:
                self.hover_frame.pack(fill="x", pady=(0, 8), before=self.scroll)
            except Exception:
                pass  # body may be collapsed / not packed

    def _add_hovered_champion(self):
        if self._hovered_champ_name:
            plist = self._get_priority_list()
            # ⚡ Bolt: Fast-path priority check with O(1) early-return
            champ_lower = self._hovered_champ_name.lower()
            in_list = any(p.lower() == champ_lower for p in plist)
                    
            if not in_list:
                plist.append(self._hovered_champ_name)
                self._save_priority_list(plist)
                self._render_grid()
                
                # Refresh button state inline
                self.hover_add_btn.configure(state="disabled", text="Added", fg_color="transparent", text_color=get_color("colors.text.disabled"))
                
                # Show toast
                try:
                    ToastManager.get_instance().show(f"Added {self._hovered_champ_name}", icon="✅", theme="success")
                except Exception:
                    pass

    # ───────────── grid rendering ─────────────
    def _render_grid(self):
        for w in self.grid_parent.winfo_children():
            w.destroy()
        self._icon_widgets.clear()

        names = self._get_priority_list()

        # Item #141: Update count badge
        if hasattr(self, "lbl_count"):
            count = len(names)
            self.lbl_count.configure(text=str(count))
            if count == 0:
                self.lbl_count.configure(fg_color=get_color("colors.text.muted"))
            else:
                self.lbl_count.configure(fg_color=get_color("colors.accent.primary"))

        if not names:
            # 🔮 Malcolm's Infusion: Interactive Empty State
            empty_btn = ctk.CTkButton(
                self.grid_parent,
                text="+\nAdd Champion",
                font=get_font("body", "bold"),
                fg_color="transparent",
                border_width=1,
                border_color=get_color("colors.border.subtle"),
                text_color=get_color("colors.text.muted"),
                hover_color=get_color("colors.background.card"),
                width=180, height=80,
                corner_radius=8,
                command=self._show_add_input,
                cursor="hand2"
            )
            empty_btn.grid(row=0, column=0, columnspan=ICONS_PER_ROW, pady=20, padx=10)
            self._icon_widgets.append((empty_btn, empty_btn, -1))
            self._sync_edit_bar_state()
            return

        # ⚡ Bolt: Lift static color lookups outside the grid generation loop and event handlers
        # to prevent repetitive string parsing overhead and optimize high-frequency hover events.
        _hover_border = get_color("colors.accent.gold", "#C8AA6E")
        _normal_border = get_color("colors.border.subtle")
        _bg_card = get_color("colors.background.card")
        _text_primary = get_color("colors.text.primary")

        cols_per_row = getattr(self, "_icons_per_row", ICONS_PER_ROW)
        for i, name in enumerate(names):
            row = i // cols_per_row
            col = i % cols_per_row

            # Slightly larger cell in edit mode to fit rank badge
            cell_size = ICON_SIZE + 4
            cell = ctk.CTkFrame(
                self.grid_parent, width=cell_size, height=cell_size,
                fg_color="transparent", corner_radius=4,
                border_width=1,
                border_color=_normal_border
            )
            # Use grid with the requested GRID_GAP
            cell.grid(
                row=row,
                column=col,
                padx=GRID_GAP // 2,
                pady=GRID_GAP // 2
            )
            cell.pack_propagate(False)

            # Set a placeholder label first
            lbl = ctk.CTkLabel(
                cell, text=name[:2], width=ICON_SIZE, height=ICON_SIZE,
                font=get_font("caption", "bold"),
                fg_color=_bg_card,
                corner_radius=4,
                text_color=_text_primary,
                cursor="hand2",
            )
            # Start with centered place for easy animation
            lbl.place(relx=0.5, rely=0.5, anchor="center")

            # Rank order badge overlay (#1, #2, #3...)
            rank_bg = get_color("colors.accent.gold", "#C8AA6E") if i < 3 else "#121C2A"
            rank_fg = "#0A1428" if i < 3 else get_color("colors.accent.gold", "#C8AA6E")
            rank_badge = ctk.CTkLabel(
                cell, text=f"#{i + 1}", width=20, height=14,
                corner_radius=4,
                fg_color=rank_bg,
                text_color=rank_fg,
                font=get_font("caption", "bold")
            )
            rank_badge.place(x=2, y=2)

            # Start async load
            def _update_icon(img, label=lbl):
                try:
                    if label.winfo_exists():
                        label.configure(image=img, text="", fg_color="transparent")
                except Exception:
                    pass

            self.assets.get_icon_async("champion", name, _update_icon, size=(ICON_SIZE, ICON_SIZE), widget=lbl)

            # Hover animations for grid
            def _on_enter(e, n=name, idx=i, c=cell, hb=_hover_border):
                self._show_tooltip(e, n, idx)
                if not self._edit_mode and idx not in self._selected_indices and idx not in self._delete_marked:
                    c.configure(border_color=hb)

            def _on_leave(e, c=cell, nb=_normal_border):
                self._hide_tooltip()
                # Item #135: Use cget() instead of accessing private c._border_color
                if not self._edit_mode:
                    try:
                        cur_border = c.cget("border_color")
                    except Exception:
                        cur_border = nb
                    if cur_border != SEL_BORDER and cur_border != DEL_BORDER:
                        c.configure(border_color=nb)

            lbl.bind("<Enter>", _on_enter)
            lbl.bind("<Leave>", _on_leave)
            
            # Drag-and-drop bindings replace cell click and shift-click
            lbl.bind("<ButtonPress-1>", lambda e=None, idx=i, label=lbl, c=cell: self._on_drag_start(e, idx, label, c))
            lbl.bind("<B1-Motion>", self._on_drag_motion)
            lbl.bind("<ButtonRelease-1>", self._on_drag_release)

            self._icon_widgets.append((cell, lbl, i))

        cols_per_row = getattr(self, "_icons_per_row", ICONS_PER_ROW)
        if hasattr(self, "grid_parent") and self.grid_parent.winfo_exists():
            for c in range(cols_per_row):
                self.grid_parent.grid_columnconfigure(c, weight=0, minsize=48)

        self._refresh_visuals()

        # Reset scrollbar position so top champion icons are always visible
        if hasattr(self, "scroll") and hasattr(self.scroll, "_parent_canvas"):
            try:
                self.scroll._parent_canvas.yview_moveto(0.0)
            except Exception:
                pass

    # ───────────── tooltip ─────────────
    def _show_tooltip(self, event, name, idx=None):
        if self._tip:
            self._hide_tooltip()
        self._tip = tk.Toplevel(self)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_attributes("-topmost", True)
        
        x = event.widget.winfo_rootx() + ICON_SIZE
        target_y = event.widget.winfo_rooty()
        start_y = target_y + 10
        self._tip.geometry(f"+{x}+{start_y}")
        self._tip.configure(bg=get_color("colors.background.card", "#1E2328"))
        
        display = f"#{idx + 1}  {name}" if idx is not None else name
        
        tip_frame = ctk.CTkFrame(
            self._tip,
            corner_radius=4,
            fg_color=get_color("colors.background.card", "#1E2328"),
            border_width=1,
            border_color=get_color("colors.accent.gold", "#C8AA6E")
        )
        tip_frame.pack()
        
        # Header (Rank and Name)
        ctk.CTkLabel(
            tip_frame, text=display,
            fg_color="transparent",
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            font=get_font("caption", "bold")
        ).pack(anchor="w", padx=8, pady=(4, 0))
                 
        # Rich Stats — pull real winrate from StatsScraper
        winrate = 50.0
        try:
            root = self.winfo_toplevel()
            scraper = getattr(root, "scraper", None)
            if scraper:
                winrate = scraper.get_winrate(name)
        except Exception:
            pass

        # Color-code the winrate
        if winrate >= 53.0:
            wr_color = get_color("colors.state.success", "#00C853")  # green — strong
        elif winrate >= 50.0:
            wr_color = get_color("colors.text.primary", "#F0E6D2")  # gold-white — neutral
        else:
            wr_color = get_color("colors.state.danger", "#ff4444")  # red — weak

        priority_label = "High" if idx is not None and idx < 3 else ("Medium" if idx is not None and idx < 7 else "Low")
        
        ctk.CTkLabel(
            tip_frame, text=f"Winrate: {winrate:.1f}%", fg_color="transparent", text_color=wr_color, justify="left",
            font=get_font("caption", "bold")
        ).pack(anchor="w", padx=8, pady=0)
        
        ctk.CTkLabel(
            tip_frame, text=f"Priority: {priority_label}", fg_color="transparent", text_color="#e0e0e0", justify="left",
            font=get_font("caption")
        ).pack(anchor="w", padx=8, pady=(0, 2))
                 
        if self._edit_mode and len(self._selected_indices) == 1 and idx not in self._selected_indices:
            ctk.CTkLabel(
                tip_frame, text="⇧Click to move here", fg_color="transparent",
                text_color=get_color("colors.accent.blue", "#4da6ff"), font=get_font("caption")
            ).pack(anchor="w", padx=8, pady=(0, 4))

        # Slide-up animation
        self._tip._current_y = start_y
        self._tip._target_y = target_y
        self._tip._x = x
        self._animate_tip_in()

    def _animate_tip_in(self):
        try:
            if not self._tip or not getattr(self._tip, "winfo_exists", lambda: False)():
                return
            if self._tip._current_y > self._tip._target_y:
                self._tip._current_y -= max(1, (self._tip._current_y - self._tip._target_y) // 2)
                self._tip.wm_geometry(f"+{self._tip._x}+{self._tip._current_y}")
                self.after(16, self._animate_tip_in)
            else:
                self._tip.wm_geometry(f"+{self._tip._x}+{self._tip._target_y}")
        except Exception:
            pass

    def _hide_tooltip(self):
        if self._tip:
            try:
                tw = self._tip
                self._tip = None
                tw.withdraw()
                tw.after(50, tw.destroy)
            except Exception:
                pass
            self._tip = None

    # ───────────── collapse ─────────────
    def _toggle_collapse(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.body.pack(fill="both", expand=True, pady=(SPACING_SM, SPACING_MD), padx=SPACING_MD)
            self.lbl_section.configure(text="▼  ARAM LIST")
        else:
            self.body.pack_forget()
            self.lbl_section.configure(text="▶  ARAM LIST")

    # ───────────── edit mode ─────────────
    def _toggle_edit_mode(self):
        self._edit_mode = not self._edit_mode
        self._selected_indices.clear()
        self._delete_marked.clear()
        if self._edit_mode:
            # Auto-expand if collapsed so the edit controls are visible
            if not self._expanded:
                self._toggle_collapse()
            self.btn_edit.configure(text="Done", text_color=get_color("colors.state.danger", "#ff4444"))
            # Staged reveal: sweep gold borders across grid cells before showing edit bar
            self._sweep_edit_borders(entering=True)
            try:
                if hasattr(self, "scroll") and self.scroll.winfo_manager():
                    self.edit_bar.pack(fill="x", padx=16, pady=(0, 8), before=self.scroll)
                else:
                    self.edit_bar.pack(fill="x", padx=16, pady=(0, 8))
            except Exception:
                self.edit_bar.pack(fill="x", padx=16, pady=(0, 8))
            # Smooth fade-in for the edit bar
            self._fade_widget(self.edit_bar, fade_in=True)
            self._sync_edit_bar_state()
            self._refresh_visuals()
            self._shake_phase = 0
            self._shake_tick()
        else:
            self.btn_edit.configure(text="Edit", text_color=get_color("colors.accent.primary"))
            self._sweep_edit_borders(entering=False)
            # Smooth fade-out then remove
            self._fade_widget(self.edit_bar, fade_in=False, on_complete=self.edit_bar.pack_forget)
            self._selected_indices.clear()
            self._refresh_visuals()

    def _sweep_edit_borders(self, entering=True):
        """Staggered gold border sweep across grid cells for edit mode transition."""
        gold = SEL_BORDER
        normal = get_color("colors.border.subtle")
        for i, (cell, lbl, idx) in enumerate(self._icon_widgets):
            if idx < 0:
                continue
            delay = i * 30  # 30ms stagger per cell
            if entering:
                # Flash gold then settle
                self.after(delay, lambda c=cell: c.configure(border_width=2, border_color=gold) if c.winfo_exists() else None)
                self.after(delay + 200, lambda c=cell: c.configure(border_width=1, border_color=normal) if c.winfo_exists() else None)
            else:
                # Brief flash then remove
                self.after(delay, lambda c=cell: c.configure(border_width=1, border_color=gold) if c.winfo_exists() else None)
                self.after(delay + 150, lambda c=cell: c.configure(border_width=0, border_color=normal) if c.winfo_exists() else None)

    def _shake_tick(self):
        """iOS-style wiggle using smooth sinusoidal motion while in edit mode."""
        if not self._edit_mode:
            # Reset all coordinates
            for cell, lbl, idx in self._icon_widgets:
                try:
                    if lbl.winfo_exists():
                        lbl.place_configure(relx=0.5, rely=0.5, x=0, y=0)
                except Exception:
                    pass
            return


        phase = self._shake_phase
        for i, (cell, lbl, idx) in enumerate(self._icon_widgets):
            try:
                if lbl.winfo_exists():
                    # Each icon gets a unique phase offset for organic feel
                    offset = phase + i * 1.2
                    dx = math.sin(offset) * 1.2
                    dy = math.cos(offset * 0.8) * 0.8
                    lbl.place_configure(relx=0.5, rely=0.5, x=int(dx), y=int(dy))
            except Exception:
                pass
        self._shake_phase = phase + 0.4
        self.after(60, self._shake_tick)

    def _sync_edit_bar_state(self):
        """Hides clear all button if the priority list is empty."""
        if self._get_priority_list():
            self.btn_clear_all.pack(side="right", padx=1, before=self.btn_del)
        else:
            self.btn_clear_all.pack_forget()

    def _on_cell_click(self, idx):
        if not self._edit_mode:
            return
        
        if idx in self._selected_indices:
            self._selected_indices.remove(idx)
        else:
            self._selected_indices.add(idx)
            
        self._refresh_visuals()

    # ───────────── drag-and-drop ─────────────
    def _on_drag_start(self, event, idx, label, cell):
        """Initiate drag. Creates a floating ghost icon."""
        if not self._edit_mode:
            # If not in edit mode, standard click (no drag)
            return

        self._drag_data["widget"] = label
        self._drag_data["cell"] = cell
        self._drag_data["idx"] = idx
        self._drag_data["start_x"] = event.x_root
        self._drag_data["start_y"] = event.y_root
        self._drag_data["ghost"] = None
        self._drag_data["is_dragging"] = False

    def _on_drag_motion(self, event):
        """Move the ghost icon with the mouse and highlight target drop cell."""
        if not self._edit_mode or not self._drag_data.get("widget"):
            return

        dx = abs(event.x_root - self._drag_data["start_x"])
        dy = abs(event.y_root - self._drag_data["start_y"])
        if not self._drag_data.get("is_dragging"):
            if dx > 4 or dy > 4:
                self._drag_data["is_dragging"] = True
                self._create_ghost_icon()
            else:
                return

        ghost = self._drag_data.get("ghost")
        if ghost and getattr(ghost, "winfo_exists", lambda: False)():
            x = event.x_root - self.winfo_toplevel().winfo_rootx() - (ICON_SIZE // 2)
            y = event.y_root - self.winfo_toplevel().winfo_rooty() - (ICON_SIZE // 2)
            ghost.place(x=x, y=y)

        # Real-time target cell highlighting during drag
        target_idx = self._find_nearest_cell_idx(event.x_root, event.y_root)
        self._highlight_drop_target(target_idx)

    def _create_ghost_icon(self):
        label = self._drag_data["widget"]
        cell = self._drag_data["cell"]
        try:
            img = label.cget("image")
            if img:
                ghost = tk.Label(self.winfo_toplevel(), image=img, bg=get_color("colors.background.app"), bd=0)
                x = self._drag_data["start_x"] - self.winfo_toplevel().winfo_rootx() - (ICON_SIZE // 2)
                y = self._drag_data["start_y"] - self.winfo_toplevel().winfo_rooty() - (ICON_SIZE // 2)
                ghost.place(x=x, y=y)
                ghost.lift()
                self._drag_data["ghost"] = ghost
                
                # Dim the source cell visually while dragging
                label.configure(image="")
                cell.configure(fg_color="#141E28", border_width=1, border_color=SEL_BORDER)
        except Exception:
            pass

    def _find_nearest_cell_idx(self, x_root, y_root):
        """Find index of nearest champion cell using exact screen coordinates."""
        best_idx = None
        min_dist_sq = float("inf")

        for cell, lbl, item_idx in self._icon_widgets:
            if item_idx < 0:
                continue
            try:
                if cell.winfo_exists() and cell.winfo_viewable():
                    cx = cell.winfo_rootx() + cell.winfo_width() // 2
                    cy = cell.winfo_rooty() + cell.winfo_height() // 2
                    dist_sq = (x_root - cx) ** 2 + (y_root - cy) ** 2
                    if dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        best_idx = item_idx
            except Exception:
                pass

        if best_idx is None:
            names = self._get_priority_list()
            best_idx = len(names) - 1 if names else 0

        return best_idx

    def _highlight_drop_target(self, target_idx):
        """Highlight the target drop cell visually during drag."""
        gold = SEL_BORDER
        normal = get_color("colors.border.subtle")
        for cell, lbl, idx in self._icon_widgets:
            if idx < 0:
                continue
            try:
                if idx == target_idx and idx != self._drag_data.get("idx"):
                    cell.configure(border_width=2, border_color=gold, fg_color=SEL_BG)
                elif idx not in self._selected_indices and idx != self._drag_data.get("idx"):
                    cell.configure(border_width=1, border_color=normal, fg_color="transparent")
            except Exception:
                pass

    def _on_drag_release(self, event):
        """Drop the icon and insert at target position."""
        if not self._edit_mode or not self._drag_data.get("widget"):
            return

        is_dragging = self._drag_data.get("is_dragging")
        idx = self._drag_data["idx"]
        
        # Cleanup ghost
        if self._drag_data.get("ghost") and getattr(self._drag_data["ghost"], "winfo_exists", lambda: False)():
            try:
                self._drag_data["ghost"].destroy()
            except Exception:
                pass
            self._drag_data["ghost"] = None

        self._drag_data["widget"] = None
        self._drag_data["is_dragging"] = False

        if not is_dragging:
            # Simple click (not drag) -> toggle cell selection
            self._on_cell_click(idx)
            return

        # Compute exact nearest target cell from drop release coordinates
        target_idx = self._find_nearest_cell_idx(event.x_root, event.y_root)
        names = self._get_priority_list()

        if target_idx is not None and 0 <= target_idx < len(names) and target_idx != idx:
            item = names.pop(idx)
            names.insert(target_idx, item)
            self._save_priority_list(names)
            self._selected_indices = {target_idx}

        self._render_grid()

    def _refresh_visuals(self):
        self._sync_edit_bar_state()
        count_sel = len(self._selected_indices)
        if hasattr(self, "btn_del") and self.btn_del.winfo_exists():
            if count_sel > 0:
                self.btn_del.configure(text=f"✕ Delete Selected ({count_sel})")
            else:
                self.btn_del.configure(text="✕ Delete Selected")

        for cell, lbl, idx in self._icon_widgets:
            if idx < 0:
                continue
            if idx in self._selected_indices:
                cell.configure(
                    fg_color=SEL_BG, border_width=2,
                    border_color=DEL_BORDER if count_sel > 1 else SEL_BORDER,
                    corner_radius=6
                )
            else:
                cell.configure(fg_color="transparent", border_width=1, border_color=get_color("colors.border.subtle"), corner_radius=4)

    def _delete_active(self):
        if not self._selected_indices:
            return
        names = self._get_priority_list()
        
        # Sort descending so popping doesn't shift the indices of earlier elements
        for idx in sorted(list(self._selected_indices), reverse=True):
            if idx < len(names):
                names.pop(idx)
                
        self._save_priority_list(names)
        self._selected_indices.clear()
        self._render_grid()

    def _request_clear_all(self):
        """Require double-click confirmation to clear the entire list."""
        if not self._clear_confirm:
            self._clear_confirm = True
            orig_text = self.btn_clear_all.cget("text")
            orig_color = self.btn_clear_all.cget("text_color")

            self.btn_clear_all.configure(text="Sure?", text_color="#e81123")

            def reset():
                if self.winfo_exists() and self._clear_confirm:
                    self._clear_confirm = False
                    self.btn_clear_all.configure(text=orig_text, text_color=orig_color)

            self.after(2000, reset)
        else:
            self._commit_clear_all()

    def _commit_clear_all(self):
        """Execute the clear operation."""
        self._clear_confirm = False
        self.btn_clear_all.configure(text="🗑️", text_color=get_color("colors.state.danger", "#ff4444"))

        names = self._get_priority_list()
        if names:
            self._save_priority_list([])
            self._selected_indices.clear()
            self._render_grid()

            ToastManager.get_instance().show(
                "ARAM List Cleared",
                icon="💥",
                theme="error",
                confetti=True
            )

    # ───────────── export / import ─────────────
    def _undo_action(self):
        if not self._undo_stack:
            return

        previous_state = self._undo_stack.pop()
        self._save_priority_list(previous_state, record_history=False)

        # Clear editing states
        self._selected_indices.clear()

        self._render_grid()
        self._sync_undo_btn()

        # Visual feedback
        pulse_color = get_color("colors.accent.primary", "#C8AA6E")
        orig_color = self.btn_undo.cget("text_color")
        self.btn_undo.configure(text_color=pulse_color)
        self.after(200, lambda: self.btn_undo.winfo_exists() and self.btn_undo.configure(text_color=orig_color))

        ToastManager.get_instance().show(
            "Undid last action",
            icon="↶",
            theme="success"
        )

    def _export_list(self):
        names = self._get_priority_list()
        if not names:
            ToastManager.get_instance().show("ARAM List is empty!", icon="⚠️", theme="error")
            return

        export_str = ", ".join(names)
        self.clipboard_clear()
        self.clipboard_append(export_str)
        self.update() # necessary to keep clipboard after window closes

        ToastManager.get_instance().show(
            "ARAM List Copied!",
            icon="📋",
            theme="success",
            confetti=True
        )

    def _show_import_preview(self):
        try:
            raw = self.clipboard_get()
        except Exception:
            ToastManager.get_instance().show("Clipboard is empty!", icon="⚠️", theme="error")
            return

        if not raw.strip():
            ToastManager.get_instance().show("Clipboard is empty!", icon="⚠️", theme="error")
            return

        # Hide add container if open
        self.add_container.pack_forget()

        # Parse comma-separated list
        potential_champs = [c.strip() for c in raw.split(",") if c.strip()]

        # Fast-path optimization using dict keys for order-preserving deduplication
        resolved_names = filter(None, (self._resolve_champion_name(p) for p in potential_champs))
        self._parsed_import = list(dict.fromkeys(resolved_names))

        if not self._parsed_import:
            ToastManager.get_instance().show("No valid champions found in clipboard.", icon="❌", theme="error")
            return

        # Show container
        self.import_container.pack(fill="x", padx=4, pady=(4, 0))
        self.lbl_import_preview.configure(text=f"Import ({len(self._parsed_import)} champs)")

        # Clear old pills
        for w in self.import_scroll.winfo_children():
            w.destroy()

        import string

        # ⚡ Bolt: Apply LICM to hoist static token resolution outside the UI render loop
        # to prevent redundant parsing and dictionary lookups on the main thread.
        _radius_sm = get_radius("sm")
        _color_card = get_color("colors.background.card")
        _color_gold = get_color("colors.accent.gold", "#C8AA6E")
        _font_caption = get_font("caption")
        _color_text_primary = get_color("colors.text.primary")

        # Render pills
        for i, champ in enumerate(self._parsed_import):
            display_name = string.capwords(champ.replace("'", "' "), " ").replace("' ", "'")
            pill = ctk.CTkFrame(
                self.import_scroll,
                corner_radius=_radius_sm,
                fg_color=_color_card,
                border_width=1,
                border_color=_color_gold
            )
            pill.pack(side="left", padx=2, pady=2)

            ctk.CTkLabel(
                pill, text=display_name,
                font=_font_caption,
                text_color=_color_text_primary
            ).pack(padx=8, pady=2)

    def _close_import(self):
        self.import_container.pack_forget()
        if hasattr(self, "add_container") and not self.add_container.winfo_viewable():
            try:
                self.add_container.pack(fill="x", pady=(0, SPACING_SM))
            except Exception:
                pass

    def _commit_import(self):
        if not self._parsed_import:
            return

        self._save_priority_list(self._parsed_import)
        self._close_import()
        self._render_grid()

        ToastManager.get_instance().show(
            f"Imported {len(self._parsed_import)} champions!",
            icon="🎉",
            theme="success"
        )

    # ───────────── add ─────────────
    def _on_add_typing(self, event):
        # Ignore navigation keys
        if event.keysym in ("Return", "Escape", "Up", "Down", "Left", "Right", "Tab"):
            return

        # ⚡ Bolt: Debounce champion search input to prevent UI thread lag from
        # O(N) widget destruction and recreation on rapid keystrokes.
        if self._debounce_timer is not None:
            self.after_cancel(self._debounce_timer)

        self._debounce_timer = self.after(150, self._perform_add_search)

    def _perform_add_search(self):
        query = self.add_entry.get().strip().lower()

        # Clear existing suggestions
        for widget in self.suggestions_frame.winfo_children():
            widget.destroy()

        if not query:
            self.suggestions_frame.pack_forget()
            return

        # Special command secret "all"
        if query == "all":
            self.suggestions_frame.pack(fill="x", pady=(4, 0))
            card = ctk.CTkFrame(
                self.suggestions_frame,
                fg_color=get_color("colors.background.card", "#192230"),
                border_width=1,
                border_color=get_color("colors.accent.gold", "#C8AA6E"),
                corner_radius=6,
                height=32
            )
            card.pack(fill="x", pady=2)
            card.pack_propagate(False)

            ctk.CTkLabel(
                card, text="✨ Add All Champions to ARAM List",
                font=get_font("caption", "bold"),
                text_color=get_color("colors.accent.gold", "#C8AA6E")
            ).pack(side="left", padx=8)

            btn = ctk.CTkButton(
                card, text="Add All", width=60, height=22,
                corner_radius=4, font=get_font("caption", "bold"),
                fg_color=get_color("colors.accent.primary"),
                hover_color=get_color("colors.state.hover"),
                command=self._commit_add, cursor="hand2"
            )
            btn.pack(side="right", padx=6)
            return

        # Alias match
        alias_champ = CHAMPION_ALIASES.get(query)
        matches = []
        if alias_champ and alias_champ.lower() in self._known_champions:
            matches.append(self._known_champions[alias_champ.lower()])

        # Starts-with matches
        for champ_lower, champ in self._search_cache:
            if champ_lower.startswith(query):
                matches.append(champ)

        # Substring matches
        for champ_lower, champ in self._search_cache:
            if query in champ_lower:
                matches.append(champ)

        unique_matches = list(dict.fromkeys(matches))

        if not unique_matches:
            self.suggestions_frame.pack_forget()
            return

        self.suggestions_frame.pack(fill="x", pady=(4, 0))
        plist = self._get_priority_list()
        plist_lower = [p.lower() for p in plist]

        for champ in unique_matches[:4]:
            card = ctk.CTkFrame(
                self.suggestions_frame,
                fg_color=get_color("colors.background.card", "#192230"),
                border_width=1,
                border_color="#253245",
                corner_radius=6,
                height=36
            )
            card.pack(fill="x", pady=2)
            card.pack_propagate(False)

            # Icon
            icon_lbl = ctk.CTkLabel(card, text="", width=28, height=28, fg_color="transparent")
            icon_lbl.pack(side="left", padx=(6, 8), pady=4)

            def _update_card_icon(img, lbl=icon_lbl):
                try:
                    if lbl.winfo_exists():
                        lbl.configure(image=img, text="")
                except Exception:
                    pass

            self.assets.get_icon_async("champion", champ, _update_card_icon, size=(28, 28), widget=icon_lbl)

            # Name
            name_lbl = ctk.CTkLabel(
                card, text=champ,
                font=get_font("body", "bold"),
                text_color=get_color("colors.text.primary", "#F0E6D2"),
                anchor="w"
            )
            name_lbl.pack(side="left", fill="x", expand=True)

            is_already_added = champ.lower() in plist_lower

            if is_already_added:
                status_lbl = ctk.CTkLabel(
                    card, text="✓ Added",
                    font=get_font("caption"),
                    text_color=get_color("colors.text.muted", "#5B5A56")
                )
                status_lbl.pack(side="right", padx=8)
            else:
                add_btn = ctk.CTkButton(
                    card, text="+ Add", width=50, height=24,
                    corner_radius=4, font=get_font("caption", "bold"),
                    fg_color=get_color("colors.accent.primary"),
                    hover_color=get_color("colors.state.hover"),
                    command=lambda c=champ: self._select_suggestion(c),
                    cursor="hand2"
                )
                add_btn.pack(side="right", padx=6)

            # Click anywhere on card to select
            if not is_already_added:
                card.bind("<Button-1>", lambda e, c=champ: self._select_suggestion(c))
                name_lbl.bind("<Button-1>", lambda e, c=champ: self._select_suggestion(c))
                icon_lbl.bind("<Button-1>", lambda e, c=champ: self._select_suggestion(c))
                card.configure(cursor="hand2")
                name_lbl.configure(cursor="hand2")
                icon_lbl.configure(cursor="hand2")

    def _select_suggestion(self, champ_name):
        plist = self._get_priority_list()
        champ_real = self._resolve_champion_name(champ_name) or champ_name
        if champ_real not in plist:
            plist.append(champ_real)
            self._save_priority_list(plist)
            self._render_grid()
            try:
                ToastManager.get_instance().show(f"Added {champ_real} to ARAM List!", icon="✅", theme="success")
            except Exception:
                pass

        self.add_entry.delete(0, "end")
        try:
            self.suggestions_frame.pack_forget()
        except Exception:
            pass
        try:
            self.add_entry.focus_set()
        except Exception:
            pass

    def _show_add_input(self):
        """Expand the ARAM list if collapsed and focus the always-visible add entry."""
        if not self._expanded:
            self._toggle_collapse()
        # Ensure add_container is packed (it may have been forgotten)
        if not self.add_container.winfo_viewable():
            try:
                self.add_container.pack(fill="x", pady=(0, SPACING_SM))
            except Exception:
                pass
        try:
            self.add_entry.focus_set()
            self.add_entry.select_range(0, "end")
        except Exception:
            pass

    def _commit_add(self):
        raw = self.add_entry.get().strip()
        if not raw:
            return

        # 🔓 Secret: "all"
        if raw.lower() == "all":
            names = self._get_priority_list()
            for champ in self._known_champions.values():
                if champ not in names:
                    names.append(champ)
            self._save_priority_list(names)
            
            self.add_entry.delete(0, "end")
            self.add_row.pack_forget()
            self._render_grid()
            return

        real_name = self._resolve_champion_name(raw)
        if real_name is None:
            self.add_entry.configure(border_color="#e81123")
            try:
                orig = self.add_entry.pack_info().get("padx", (0, 4))
                self._shake_widget(self.add_entry, orig)
            except Exception:
                pass
            self.after(1200, lambda: self.add_entry.configure(
                border_color=get_color("colors.border.subtle")))
            return

        names = self._get_priority_list()
        if real_name not in names:
            names.append(real_name)
            self._save_priority_list(names)
        self.add_entry.delete(0, "end")
        try:
            self.suggestions_frame.pack_forget()
        except Exception:
            pass
        # Keep add_container visible — don't hide it after adding
        self._render_grid()
        try:
            self.add_entry.focus_set()
        except Exception:
            pass

    # ───────────── animation helpers ─────────────
    def _shake_widget(self, widget, orig_padx, amplitude=6, steps=6):
        """Horizontal shake animation for invalid input feedback."""
        offsets = []
        for s in range(steps):
            direction = 1 if s % 2 == 0 else -1
            mag = max(1, int(amplitude * (1 - s / steps)))
            offsets.append(direction * mag)
        offsets.append(0)  # return to rest

        def _step(i):
            try:
                if not widget.winfo_exists():
                    return
                pad = offsets[i]
                widget.pack_configure(padx=(pad, 4))
                if i < len(offsets) - 1:
                    self.after(40, lambda: _step(i + 1))
                else:
                    # Restore original padding
                    widget.pack_configure(padx=orig_padx if isinstance(orig_padx, tuple) else (orig_padx, 4))
            except Exception:
                pass

        _step(0)

    def _fade_widget(self, widget, fade_in=True, on_complete=None, steps=5):
        """Smooth opacity transition for edit mode bar.

        Uses incremental alpha on child labels/buttons since CTkFrame doesn't
        support global opacity.  Falls back to instant show/hide if the widget
        tree is unavailable.
        """
        try:
            children = widget.winfo_children()
            if not children:
                if on_complete:
                    on_complete()
                return

            if fade_in:
                # Start transparent, end opaque
                alphas = [i / steps for i in range(1, steps + 1)]
            else:
                alphas = [1 - i / steps for i in range(1, steps + 1)]

            def _apply(step):
                if step >= len(alphas):
                    if on_complete:
                        on_complete()
                    return
                # For CTk widgets, we approximate opacity with text_color alpha
                # by slightly dimming. Full opacity control isn't available,
                # so we just stagger visibility.
                if step == 0 and fade_in:
                    for child in children:
                        try:
                            child.configure(text_color=get_color("colors.text.disabled"))
                        except Exception:
                            pass
                elif step == len(alphas) - 1:
                    for child in children:
                        try:
                            if fade_in:
                                child.configure(text_color=child._text_color if hasattr(child, '_text_color') else get_color("colors.text.primary"))
                        except Exception:
                            pass
                self.after(30, lambda: _apply(step + 1))

            _apply(0)
        except Exception:
            if on_complete:
                on_complete()
