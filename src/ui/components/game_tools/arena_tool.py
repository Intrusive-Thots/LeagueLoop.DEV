import os
import customtkinter as ctk

from ui.components.factory import get_color, get_font
from ui.components.champion_input import ChampionInput
from ui.components.toast import ToastManager
from utils.path_utils import get_asset_path
from utils.logger import Logger

_CLEAN_TRANS = str.maketrans("", "", " '.")

class ArenaTool(ctk.CTkFrame):
    """Arena Synergy Picker V5: Rebuilt from the ground up."""

    def __init__(self, master, config, assets, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.config = config
        self.assets = assets

        self._known_champions = self._scan_known_champions()
        self._active_pair_idx = -1

        self._build_ui()
        self._render_pairs()

    # ───────────── Data Helpers ─────────────
    def _scan_known_champions(self):
        known = {}
        cache_dir = get_asset_path("assets")
        if os.path.isdir(cache_dir):
            for f in os.listdir(cache_dir):
                if f.startswith("champion_") and f.endswith(".png"):
                    real = f[len("champion_"):-len(".png")]
                    known[real.lower()] = real
        self._search_cache = sorted([(v.lower(), v) for v in known.values()], key=lambda x: x[1])
        return known

    def _resolve_champion_name(self, raw):
        res = self._known_champions.get(raw)
        if res: return res
        normalized = raw.translate(_CLEAN_TRANS).lower()
        return self._known_champions.get(normalized)

    def _get_pairs(self):
        return self.config.get("arena_pairs", [])

    def _save_pairs(self, pairs):
        self.config.set("arena_pairs", pairs)
        self._render_pairs()

    def _update_header_count(self):
        pairs = self._get_pairs()
        count = len(pairs)
        if count > 0:
            enabled_count = sum(1 for p in pairs if p.get("enabled", True))
            self.lbl_count.configure(text=f"({enabled_count}/{count})")
        else:
            self.lbl_count.configure(text="")

    # ───────────── UI Build ─────────────
    def _build_ui(self):
        from ui.components.factory import make_card, make_divider, make_button
        from ui.components.settings_row import SettingsToggleRow

        self.card = make_card(
            self,
            title="ARENA SYNERGY",
            padx=0,
            pady=0,
            collapsible=True,
            start_collapsed=False
        )

        # Inject count label into header
        self.lbl_count = ctk.CTkLabel(
            self.card._header, text="", font=("Inter", 9, "bold"),
            text_color=get_color("colors.accent.purple", "#A855F7"), anchor="w", width=20
        )
        self.lbl_count.pack(side="left", padx=(2, 0))
        self.lbl_count.configure(cursor="hand2")
        self.lbl_count.bind("<Button-1>", self.card._toggle_controller.toggle)

        # The rest goes into self.card
        self.body = self.card

        # Row 1: Master Enable
        self.var_synergy_enabled = ctk.BooleanVar(value=self.config.get("arena_synergy_enabled", True))
        self.sw_synergy = SettingsToggleRow(
            self.body, 
            label_text="⚡ Enable Synergy", 
            variable=self.var_synergy_enabled,
            command=self._on_toggle_synergy,
            height=28
        )
        self.sw_synergy.pack(fill="x", padx=10, pady=(5, 0))

        # Row 2: Auto-Lock
        self.var_auto_lock = ctk.BooleanVar(value=self.config.get("arena_auto_lock", False))
        self.sw_auto_lock = SettingsToggleRow(
            self.body,
            label_text="🔒 Auto-Lock Pick",
            variable=self.var_auto_lock,
            command=self._on_toggle_auto_lock,
            height=28
        )
        self.sw_auto_lock.pack(fill="x", padx=10, pady=(4, 0))
        
        # Row 3: Instant Ban
        self.var_instant_ban = ctk.BooleanVar(value=self.config.get("arena_instant_ban", False))
        self.sw_instant_ban = SettingsToggleRow(
            self.body,
            label_text="⚡ Instant Ban",
            variable=self.var_instant_ban,
            command=self._on_toggle_instant_ban,
            height=28
        )
        self.sw_instant_ban.pack(fill="x", padx=10, pady=(4, 0))

        make_divider(self.body, padx=10, pady=(8, 8))

        # Row 4: Auto Ban
        self.ban_row = ctk.CTkFrame(self.body, fg_color="transparent", height=28)
        self.ban_row.pack_propagate(False)
        self.ban_row.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkLabel(self.ban_row, text="🚫 Auto Ban", font=get_font("body"), text_color=get_color("colors.text.primary")).pack(side="left")
        self.entry_ban = ChampionInput(self.ban_row, placeholder="None", width=120, height=26, on_commit=self._on_ban_updated)
        self.entry_ban.pack(side="right")
        self.entry_ban.insert(0, self.config.get("arena_ban", ""))
        self.entry_ban.bind("<FocusOut>", lambda e: self._on_ban_updated())

        # Row 5: Fallback Pick
        self.fallback_row = ctk.CTkFrame(self.body, fg_color="transparent", height=28)
        self.fallback_row.pack_propagate(False)
        self.fallback_row.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(self.fallback_row, text="❔ Fallback Pick", font=get_font("body"), text_color=get_color("colors.text.primary")).pack(side="left")
        self.entry_fallback = ChampionInput(self.fallback_row, placeholder="None", width=120, height=26, on_commit=self._on_fallback_updated)
        self.entry_fallback.pack(side="right")
        self.entry_fallback.insert(0, self.config.get("arena_fallback_pick", ""))
        self.entry_fallback.bind("<FocusOut>", lambda e: self._on_fallback_updated())

        make_divider(self.body, padx=10, pady=(0, 8))

        # Add Pair Section
        ctk.CTkLabel(self.body, text="Create New Synergy", font=get_font("caption", "bold"), text_color=get_color("colors.accent.gold", "#C8AA6E")).pack(anchor="w", padx=10, pady=(0, 2))
        
        self.add_inputs = ctk.CTkFrame(self.body, fg_color="transparent")
        self.add_inputs.pack(fill="x", padx=10, pady=(0, 8))
        
        self.entry_teammate = ChampionInput(self.add_inputs, placeholder="Teammate...", width=90, height=24)
        self.entry_teammate.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
        self.entry_me = ChampionInput(self.add_inputs, placeholder="I will play...", width=90, height=24, on_commit=lambda c: self._add_pair())
        self.entry_me.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_add = make_button(
            self.add_inputs, text="Add", width=40, height=24,
            command=self._add_pair
        )
        self.btn_add.pack(side="right")

        # List Area
        self.list_frame = ctk.CTkScrollableFrame(
            self.body, fg_color="transparent", height=160,
            scrollbar_button_color=get_color("colors.text.disabled"),
            scrollbar_button_hover_color=get_color("colors.text.muted"), scrollbar_fg_color="transparent"
        )
        try:
            # Reaching into CustomTkinter's private `_scrollbar` is fragile by
            # nature — it is not API and has moved between releases — so a
            # failure here means a slightly wider scrollbar, not a broken
            # screen. Worth a line in the log all the same, because "the
            # scrollbar looks wrong after an upgrade" is otherwise unfindable.
            self.list_frame._scrollbar.configure(width=6)
        except Exception as exc:
            Logger.debug("ArenaTool", "Could not thin the scrollbar", exc=exc)
        self.list_frame.pack(fill="x", padx=10, pady=(0, 10))

    # ───────────── Callbacks ─────────────
    def _on_toggle_synergy(self):
        self.config.set("arena_synergy_enabled", self.var_synergy_enabled.get())

    def _on_toggle_auto_lock(self):
        self.config.set("arena_auto_lock", self.var_auto_lock.get())
        
    def _on_toggle_instant_ban(self):
        self.config.set("arena_instant_ban", self.var_instant_ban.get())

    def _on_ban_updated(self, resolved=None):
        if not resolved:
            val = self.entry_ban.get().strip()
            if not val:
                self.config.set("arena_ban", "")
                self.entry_ban.delete(0, "end")
                return
            resolved = self._resolve_champion_name(val)
            
        if resolved:
            self.entry_ban.delete(0, "end")
            self.entry_ban.insert(0, resolved)
            self.config.set("arena_ban", resolved)
        else:
            saved = self.config.get("arena_ban", "")
            self.entry_ban.delete(0, "end")
            self.entry_ban.insert(0, saved)
            self._flash_entry(self.entry_ban)

    def _on_fallback_updated(self, resolved=None):
        if not resolved:
            val = self.entry_fallback.get().strip()
            if not val:
                self.config.set("arena_fallback_pick", "")
                self.entry_fallback.delete(0, "end")
                return
            resolved = self._resolve_champion_name(val)
            
        if resolved:
            self.entry_fallback.delete(0, "end")
            self.entry_fallback.insert(0, resolved)
            self.config.set("arena_fallback_pick", resolved)
        else:
            saved = self.config.get("arena_fallback_pick", "")
            self.entry_fallback.delete(0, "end")
            self.entry_fallback.insert(0, saved)
            self._flash_entry(self.entry_fallback)

    def _flash_entry(self, entry):
        entry.configure(border_color="#e81123")
        self.after(800, lambda: entry.winfo_exists() and entry.configure(border_color=get_color("colors.border.subtle")))

    def _add_pair(self):
        tm_raw = self.entry_teammate.get().strip()
        me_raw = self.entry_me.get().strip()
        
        tm_resolved = self._resolve_champion_name(tm_raw)
        me_resolved = self._resolve_champion_name(me_raw)
        
        if not tm_resolved:
            self._flash_entry(self.entry_teammate)
            return
        if not me_resolved:
            self._flash_entry(self.entry_me)
            return

        pairs = self._get_pairs()
        updated = False
        
        for pair in pairs:
            if pair.get("teammate", "").lower() == tm_resolved.lower():
                if me_resolved not in pair.get("me", []):
                    pair["me"].append(me_resolved)
                updated = True
                break

        if not updated:
            pairs.append({"teammate": tm_resolved, "me": [me_resolved], "enabled": True})

        self._save_pairs(pairs)
        self.entry_teammate.delete(0, "end")
        self.entry_me.delete(0, "end")
        self.entry_teammate.focus_set()
        
        try:
            ToastManager.get_instance().show(f"Added: {tm_resolved} → {me_resolved}", icon="🤝", theme="success")
        except Exception as exc:
            Logger.debug("ArenaTool", "_add_pair suppressed an error", exc=exc)

    def _toggle_pair(self, idx):
        pairs = self._get_pairs()
        if 0 <= idx < len(pairs):
            pairs[idx]["enabled"] = not pairs[idx].get("enabled", True)
            self._save_pairs(pairs)

    def _delete_pair(self, idx):
        pairs = self._get_pairs()
        if 0 <= idx < len(pairs):
            pairs.pop(idx)
            self._save_pairs(pairs)

    def _remove_fallback(self, pair_idx, fallback_idx):
        pairs = self._get_pairs()
        if 0 <= pair_idx < len(pairs):
            my_list = pairs[pair_idx].get("me", [])
            if 0 <= fallback_idx < len(my_list):
                my_list.pop(fallback_idx)
                if not my_list:
                    pairs.pop(pair_idx)
                self._save_pairs(pairs)

    def set_active_pair(self, idx):
        if idx != self._active_pair_idx:
            self._active_pair_idx = idx
            self._render_pairs()


    def _render_pairs(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        pairs = self._get_pairs()
        self._update_header_count()

        if not pairs:
            ctk.CTkLabel(self.list_frame, text="No synergies created yet.\nAdd a teammate and your pick above.", font=get_font("caption"), text_color=get_color("colors.text.muted"), justify="center").pack(pady=20)
            return

        for i, pair in enumerate(pairs):
            is_enabled = pair.get("enabled", True)
            is_active = (i == self._active_pair_idx)

            card_bg = get_color("colors.background.card") if is_enabled else get_color("colors.background.disabled", "#0A0E14")
            if is_active:
                border_color = get_color("colors.accent.purple", "#A855F7")
            else:
                border_color = get_color("colors.border.subtle")

            row = ctk.CTkFrame(self.list_frame, fg_color=card_bg, corner_radius=6, border_width=1 if is_active else 0, border_color=border_color)
            row.pack(fill="x", pady=2)
            
            top_bar = ctk.CTkFrame(row, fg_color="transparent")
            top_bar.pack(fill="x", padx=6, pady=(6, 2))

            tm_name = pair.get("teammate", "Unknown")
            tm_color = get_color("colors.accent.blue", "#3B82F6") if is_enabled else get_color("colors.text.disabled")
            
            ctk.CTkLabel(top_bar, text="IF", font=("Inter", 9, "bold"), text_color=get_color("colors.text.disabled")).pack(side="left", padx=(0, 4))
            ctk.CTkLabel(top_bar, text=tm_name, font=get_font("caption", "bold"), text_color=tm_color).pack(side="left")

            btn_del = ctk.CTkButton(top_bar, text="✕", width=20, height=20, corner_radius=4, fg_color="transparent", text_color=get_color("colors.text.muted"), hover_color=get_color("colors.state.danger.muted", "#4d1111"), command=lambda idx=i: self._delete_pair(idx), cursor="hand2")
            btn_del.pack(side="right")
            
            btn_tog = ctk.CTkButton(top_bar, text="ON" if is_enabled else "OFF", width=30, height=20, corner_radius=4, fg_color=get_color("colors.state.success.muted") if is_enabled else "transparent", text_color=get_color("colors.state.success") if is_enabled else get_color("colors.text.muted"), hover_color=get_color("colors.state.hover"), command=lambda idx=i: self._toggle_pair(idx), cursor="hand2")
            btn_tog.pack(side="right", padx=4)

            # Fallbacks
            me_list = pair.get("me", [])
            tag_frame = ctk.CTkFrame(row, fg_color="transparent")
            tag_frame.pack(fill="x", padx=6, pady=(2, 6))
            
            ctk.CTkLabel(tag_frame, text="THEN", font=("Inter", 9, "bold"), text_color=get_color("colors.text.disabled")).pack(side="left", padx=(0, 4))
            
            for j, champ in enumerate(me_list):
                tag_color = get_color("colors.state.success", "#00C853") if j == 0 else get_color("colors.text.muted")
                if not is_enabled: tag_color = get_color("colors.text.disabled")
                
                tag = ctk.CTkFrame(tag_frame, fg_color=get_color("colors.background.app"), corner_radius=4, border_width=1, border_color=get_color("colors.border.subtle"))
                tag.pack(side="left", padx=2)
                
                ctk.CTkLabel(tag, text=f"#{j+1}", font=("Inter", 8, "bold"), text_color=get_color("colors.text.disabled")).pack(side="left", padx=(4, 2))
                ctk.CTkLabel(tag, text=champ, font=get_font("caption"), text_color=tag_color).pack(side="left", padx=2)
                ctk.CTkButton(tag, text="✕", width=16, height=16, corner_radius=4, font=("Inter", 10), fg_color="transparent", text_color=get_color("colors.text.muted"), hover_color=get_color("colors.state.danger.muted", "#4d1111"), command=lambda pid=i, fid=j: self._remove_fallback(pid, fid), cursor="hand2").pack(side="right", padx=(0, 2))
