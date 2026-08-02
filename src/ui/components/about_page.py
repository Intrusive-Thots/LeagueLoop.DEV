import customtkinter as ctk

from ui.components.factory import get_color, get_font, get_radius

class AboutPage(ctk.CTkToplevel):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.title("About LeagueLoop")
        self.geometry("460x420")
        self._egg_clicks = 0
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=get_color("colors.background.app"))
        
        self.update_idletasks()
        try:
            x = master.winfo_rootx() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
            y = master.winfo_rooty() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{int(x)}+{int(y)}")
        except Exception:
            pass
            
        self._setup_ui()
        self.focus_force()
        
        # Bind Escape key to close window
        self.bind("<Escape>", lambda e: self.destroy())

    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color=get_color("colors.background.app", "#0A1428"), corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="ⓘ  INFO & ABOUT",
            font=("Beaufort for LOL", 16, "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
        ).pack(side="left", padx=16, pady=16)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            body, 
            text="LeagueLoop is a companion overlay application designed to automate\n"
                 "and streamline League of Legends lobbies and matchmaking.",
            font=get_font("body"),
            text_color=get_color("colors.text.primary"),
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            body, 
            text="How it works:\n"
                 "It interfaces directly with the official League Client Update (LCU) API\n"
                 "to safely read client state and send lobby commands automatically,\n"
                 "bypassing manual clicks without modifying game files.",
            font=get_font("body"),
            text_color=get_color("colors.text.muted"),
            justify="left"
        ).pack(anchor="w", pady=(0, 16))

        disclaimer_frame = ctk.CTkFrame(body, fg_color=get_color("colors.background.card"), corner_radius=get_radius("md"))
        disclaimer_frame.pack(fill="x", pady=(0, 16))
        
        ctk.CTkLabel(
            disclaimer_frame, 
            text="LEGAL & LIABILITY WAIVER",
            font=get_font("caption", "bold"),
            text_color=get_color("colors.state.danger", "#e81123"),
        ).pack(anchor="w", padx=12, pady=(12, 4))
        
        ctk.CTkLabel(
            disclaimer_frame, 
            text="LeagueLoop was created under Riot Games' policy using assets\n"
                 "owned by Riot Games. Riot Games does not endorse or sponsor\n"
                 "this project. Furthermore, the creator is NOT liable for any\n"
                 "account suspensions, spontaneous PC combustion, or emotional\n"
                 "damage incurred while using this software. Use entirely at\n"
                 "your own risk.",
            font=get_font("caption"),
            text_color=get_color("colors.text.muted"),
            justify="left"
        ).pack(anchor="w", padx=12, pady=(0, 12))

        # Close Button
        btn_close = ctk.CTkButton(
            body,
            text="Close",
            font=get_font("body", "bold"),
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            hover_color=get_color("colors.state.hover"),
            border_width=1,
            border_color=get_color("colors.border.subtle"),
            command=self.destroy,
            height=30
        )
        btn_close.pack(fill="x", side="bottom", pady=(0, 12))

        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(fill="x", side="bottom")

        self.lbl_author = ctk.CTkLabel(
            footer, text="Made by Malcolm",
            font=get_font("body", "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            cursor="hand2",
        )
        self.lbl_author.pack(side="left")

        # Malcolm's Easter Egg bindings
        self.lbl_author.bind("<Button-1>", self._on_author_click)
        self.lbl_author.bind("<Enter>", lambda e: self.lbl_author.configure(text_color=get_color("colors.text.primary", "#F0E6D2")))
        self.lbl_author.bind("<Leave>", lambda e: self.lbl_author.configure(text_color=get_color("colors.accent.gold", "#C8AA6E") if self._egg_clicks < 5 else get_color("colors.accent.purple", "#A855F7")))

        ctk.CTkLabel(
            footer, text="Banned.Malcolm@gmail.com",
            font=get_font("body", "bold"),
            text_color=get_color("colors.text.disabled", "#4B5E73"),
        ).pack(side="right")

    def _on_author_click(self, event=None):
        if self._egg_clicks >= 5:
            return

        self._egg_clicks += 1

        if self._egg_clicks == 5:
            self.lbl_author.configure(text_color="#A855F7")
            try:
                from ui.components.toast import ToastManager
                # Try to get the main app root
                root = self.master.master if hasattr(self.master, "master") else self.master
                ToastManager.get_instance(root).show(
                    message="You found a Poro Snack! 🍪",
                    icon="✨",
                    duration=4000,
                    theme="success",
                    confetti=True
                )
            except Exception as e:
                from utils.logger import Logger
                Logger.error("AboutPage", f"Easter egg error: {e}")
