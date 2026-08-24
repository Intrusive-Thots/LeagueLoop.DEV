import customtkinter as ctk

from ui.components.factory import get_color, get_font, get_radius
from ui.components.champion_input import ChampionInput
from ui.ui_shared import CTkTooltip
from core.constants import SPACING_SM, SPACING_MD
from utils.logger import Logger

class DraftTool(ctk.CTkFrame):
    """Draft Assistant: Auto-hovers and auto-bans based on assigned position."""

    ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

    def __init__(self, master, config, assets, **kw):
        super().__init__(master, fg_color=get_color("colors.background.panel", "#0F1A24"), corner_radius=get_radius("md"), **kw)
        self.config = config
        self.assets = assets

        self._expanded = False
        self._entries = {}  # { "TOP_pick_1": CTkEntry, ... }
        
        self._build_header()
        self._build_body()
        self._load_config()

    def _build_header(self):
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=24)
        self.header.pack(fill="x", padx=SPACING_MD, pady=(SPACING_MD, 0))

        self.lbl_section = ctk.CTkLabel(
            self.header, text="▶  DRAFT ASSISTANT",
            font=get_font("caption", "bold"),
            text_color=get_color("colors.text.muted"), anchor="w",
            cursor="hand2"
        )
        self.lbl_section.pack(side="left", padx=2)
        CTkTooltip(self.lbl_section, "Toggle Role Enforcer Settings")
        
        self.lbl_section.bind("<Button-1>", lambda e: self._toggle_collapse())
        self.lbl_section.bind("<Enter>", lambda e: self.lbl_section.configure(text_color=get_color("colors.text.primary")))
        self.lbl_section.bind("<Leave>", lambda e: self.lbl_section.configure(text_color=get_color("colors.text.muted")))

    def _build_body(self):
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        
        # Tab View
        self.tabview = ctk.CTkTabview(
            self.body,
            width=280, height=200,
            fg_color=get_color("colors.background.card"),
            segmented_button_fg_color=get_color("colors.background.app", "#0A1428"),
            segmented_button_selected_color=get_color("colors.accent.primary"),
            segmented_button_selected_hover_color=get_color("colors.state.hover"),
            segmented_button_unselected_hover_color=get_color("colors.state.hover"),
            text_color=get_color("colors.text.primary")
        )
        self.tabview.pack(fill="both", expand=True, padx=4, pady=4)
        
        # We rename the labels to be shorter for UI
        display_roles = {"TOP": "Top", "JUNGLE": "Jg", "MIDDLE": "Mid", "BOTTOM": "Adc", "UTILITY": "Sup"}
        
        for role in self.ROLES:
            tab_name = display_roles[role]
            self.tabview.add(tab_name)
            tab = self.tabview.tab(tab_name)
            
            # Pick Priority Column
            pick_frame = ctk.CTkFrame(tab, fg_color="transparent")
            pick_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))
            ctk.CTkLabel(pick_frame, text="Picks", font=get_font("caption", "bold"), text_color=get_color("colors.state.success")).pack(anchor="w")
            
            for i in range(1, 4):
                key = f"pick_{role}_{i}"
                entry = ChampionInput(pick_frame, placeholder=f"Pick {i}", height=28)
                entry.pack(fill="x", pady=2)
                self._entries[key] = entry
                
            # Ban Priority Column
            ban_frame = ctk.CTkFrame(tab, fg_color="transparent")
            ban_frame.pack(side="right", fill="both", expand=True, padx=(4, 0))
            ctk.CTkLabel(ban_frame, text="Bans", font=get_font("caption", "bold"), text_color=get_color("colors.state.warning", "#E67E22")).pack(anchor="w")
            
            for i in range(1, 4):
                key = f"ban_{role}_{i}"
                entry = ChampionInput(ban_frame, placeholder=f"Ban {i}", height=28)
                entry.pack(fill="x", pady=2)
                self._entries[key] = entry
                
        # Save Button
        self.btn_save = ctk.CTkButton(
            self.body, text="Save Draft Profile", height=28,
            font=get_font("body", "bold"),
            fg_color=get_color("colors.accent.primary"), text_color="#ffffff",
            hover_color=get_color("colors.state.hover"),
            command=self._save_config
        )
        self.btn_save.pack(fill="x", pady=(SPACING_MD, 0), padx=4)

    def _toggle_collapse(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.body.pack(fill="both", expand=True, pady=(SPACING_SM, SPACING_MD), padx=SPACING_MD)
            self.lbl_section.configure(text="▼  DRAFT ASSISTANT")
        else:
            self.body.pack_forget()
            self.lbl_section.configure(text="▶  DRAFT ASSISTANT")

    def _load_config(self):
        for role in self.ROLES:
            for i in range(1, 4):
                p_key = f"pick_{role}_{i}"
                b_key = f"ban_{role}_{i}"
                self._entries[p_key].insert(0, self.config.get(p_key, ""))
                self._entries[b_key].insert(0, self.config.get(b_key, ""))

    def _save_config(self):
        saved_count = 0
        for key, entry in self._entries.items():
            val = entry.get().strip()
            # Item #126: Use the entry's resolved value if available,
            # avoiding .title() which corrupts multi-word names like "Dr. Mundo"
            if hasattr(entry, 'resolved_name') and entry.resolved_name:
                val = entry.resolved_name
            elif val:
                # Fallback: capitalize first letter of each word but preserve existing casing
                val = val.strip()
            self.config.set(key, val)
            if val:
                saved_count += 1
                
        # Quick flash logic for success UI
        orig_text = self.btn_save.cget("text")
        orig_color = self.btn_save.cget("fg_color")
        self.btn_save.configure(text="✓ Saved", fg_color=get_color("colors.state.success", "#00C853"))
        
        try:
            from ui.components.toast import ToastManager
            ToastManager.get_instance().show("Draft Profiles Saved", theme="success", icon="🛡️")
        except Exception as exc:
            Logger.debug("DraftTool", "_save_config suppressed an error", exc=exc)

        # Item #132: Store timer ID so it can be cancelled if widget is destroyed
        self._revert_timer = self.after(1000, self._revert_save_button, orig_text, orig_color)

    def _revert_save_button(self, text, color):
        """Safely revert save button text after flash."""
        if self.winfo_exists() and self.btn_save.winfo_exists():
            self.btn_save.configure(text=text, fg_color=color)

    def destroy(self):
        if getattr(self, "_revert_timer", None) is not None:
            try:
                self.after_cancel(self._revert_timer)
                self._revert_timer = None
            except Exception as exc:
                Logger.debug("DraftTool", "destroy suppressed an error", exc=exc)
        super().destroy()

