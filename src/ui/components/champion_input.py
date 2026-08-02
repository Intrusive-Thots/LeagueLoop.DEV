import os
import string
import customtkinter as ctk

from utils.path_utils import get_asset_path, get_data_dir
from ui.components.factory import get_color, get_font, make_input

_CLEAN_TRANS = str.maketrans("", "", " '.")

class ChampionInput(ctk.CTkFrame):
    def __init__(self, master, width=120, height=28, placeholder="Champion...", on_commit=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_commit = on_commit
        
        self.entry = make_input(self, width=width, height=height, placeholder=placeholder, font=get_font("caption"))
        self.entry.pack(fill="x")
        
        # We need to forward methods so it can be used as a drop-in replacement for CTkEntry
        self.get = self.entry.get
        self.insert = self.entry.insert
        self.delete = self.entry.delete
        self.configure = self.entry.configure
        self.cget = self.entry.cget
        self.bind = self.entry.bind
        self.unbind = self.entry.unbind
        self.focus_set = self.entry.focus_set

        self.entry.bind("<KeyRelease>", self._on_typing, add="+")
        self.entry.bind("<Return>", lambda e: self._handle_return(), add="+")
        self.entry.bind("<FocusOut>", self._on_focus_out, add="+")
        
        self.suggestions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._debounce_timer = None
        
        self._known_champions = {}
        self._search_cache = []
        self._scan_known_champions()

    def _scan_known_champions(self):
        # Bundled assets
        cache_dir = get_asset_path("assets")
        self._load_from_dir(cache_dir)
        # Downloaded cache
        app_cache_dir = os.path.join(get_data_dir(), "cache", "assets")
        self._load_from_dir(app_cache_dir)
        
        self._search_cache = sorted(
            [(v.lower(), v, string.capwords(v.replace("'", "' "), " ").replace("' ", "'")) for v in self._known_champions.values()], key=lambda x: x[1]
        )

    def _load_from_dir(self, d):
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.startswith("champion_") and f.endswith(".png"):
                    real = f[len("champion_"):-len(".png")]
                    self._known_champions[real.lower()] = real

    def _resolve_champion_name(self, raw):
        res = self._known_champions.get(raw)
        if res: return res
        normalized = raw.translate(_CLEAN_TRANS).lower()
        return self._known_champions.get(normalized)

    def _on_typing(self, event):
        if event.keysym in ("Return", "Escape", "Up", "Down", "Left", "Right", "Tab"):
            if event.keysym == "Escape":
                self.suggestions_frame.pack_forget()
            return

        if self._debounce_timer is not None:
            self.after_cancel(self._debounce_timer)
        self._debounce_timer = self.after(150, self._perform_add_search)

    def _on_focus_out(self, event):
        # Delay hiding to allow clicks on suggestions
        self.after(200, self.suggestions_frame.pack_forget)

    def _perform_add_search(self):
        query = self.entry.get().strip().lower()

        for widget in self.suggestions_frame.winfo_children():
            widget.destroy()

        if not query:
            self.suggestions_frame.pack_forget()
            return

        matches = []
        for champ_lower, champ, display_name in self._search_cache:
            if champ_lower.startswith(query):
                matches.append((champ, display_name))
            elif query in champ_lower:
                matches.append((champ, display_name))

        unique_matches = list(dict.fromkeys(matches))

        if not unique_matches:
            self.suggestions_frame.pack_forget()
            return

        self.suggestions_frame.pack(fill="x", pady=(2, 0))

        for i, (champ, display_name) in enumerate(unique_matches[:3]):
            pill = ctk.CTkButton(
                self.suggestions_frame, text=display_name, width=0, height=20,
                corner_radius=10, font=get_font("caption"),
                fg_color=get_color("colors.background.card"),
                border_width=1, border_color=get_color("colors.accent.gold", "#c8aa6e"),
                hover_color=get_color("colors.state.hover"),
                text_color=get_color("colors.text.primary"),
                command=lambda raw=champ: self._select_suggestion(raw), cursor="hand2",
            )
            pill.pack(side="left", padx=(0, 2))

    def _select_suggestion(self, raw_name):
        self.entry.delete(0, "end")
        self.entry.insert(0, raw_name)
        self.entry.configure(border_color=get_color("colors.accent.primary"))
        self.suggestions_frame.pack_forget()

        def finalize():
            if self.entry.winfo_exists():
                self.entry.configure(border_color=get_color("colors.border.subtle"))
            if self.on_commit:
                # Use after to prevent blocking UI thread
                self.after(50, lambda: self.on_commit(raw_name))

        self.after(150, finalize)

    def _handle_return(self):
        self.suggestions_frame.pack_forget()
        raw = self.entry.get().strip()
        if not raw:
            return
        resolved = self._resolve_champion_name(raw)
        if resolved:
            self.entry.delete(0, "end")
            self.entry.insert(0, resolved)
            if self.on_commit:
                self.on_commit(resolved)
        else:
            self.entry.configure(border_color="#e81123")
            self.after(800, lambda: self.entry.configure(border_color=get_color("colors.border.subtle")))
