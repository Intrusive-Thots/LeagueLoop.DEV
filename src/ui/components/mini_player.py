import customtkinter as ctk # type: ignore
from ui.components.factory import get_color, get_font # type: ignore
from ui.ui_shared import CTkTooltip # type: ignore
from utils.logger import Logger # type: ignore

class MiniPlayer(ctk.CTkToplevel):
    def __init__(self, master, config=None, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.config = config

        self.title("LeagueLoop Mini")
        self.geometry("400x60")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=get_color("colors.background.card"))

        self._drag_data = {"x": 0, "y": 0}

        self._build_ui()
        self._bind_events()
        
        # Start hidden
        self.withdraw()

    def _build_ui(self):
        self.lbl_status = ctk.CTkLabel(
            self, text="Idle",
            font=get_font("body", "bold"),
            text_color=get_color("colors.text.primary")
        )
        self.lbl_status.pack(side="left", padx=16)

        self.btn_close = ctk.CTkButton(
            self, text="×", width=30, height=30,
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover"),
            command=self.hide
        )
        self.btn_close.pack(side="right", padx=8)
        CTkTooltip(self.btn_close, "Hide Compact Tracker")
        
        self.btn_restore = ctk.CTkButton(
            self, text="[ ]", width=30, height=30,
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover"),
            command=self._restore_main
        )
        self.btn_restore.pack(side="right", padx=4)
        CTkTooltip(self.btn_restore, "Restore Full Window")

    def _bind_events(self):
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag(self, event):
        x = self.winfo_x() - self._drag_data["x"] + event.x
        y = self.winfo_y() - self._drag_data["y"] + event.y
        self.geometry(f"+{x}+{y}")

    def update_state(self, phase: str):
        try:
            self.lbl_status.configure(text=f"Phase: {phase}")
        except Exception:
            pass

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide(self):
        self.withdraw()
        
    def toggle(self):
        if self.state() == "withdrawn":
            self.show()
        else:
            self.hide()

    def _restore_main(self):
        self.hide()
        if hasattr(self.master, "deiconify"):
            self.master.deiconify()
            self.master.lift()
