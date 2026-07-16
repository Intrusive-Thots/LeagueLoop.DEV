"""
Sidebar Status Bar Component
Displays LCU action log statuses and provides log control.
"""
import customtkinter as ctk
from ui.components.factory import get_color, get_font
from ui.ui_shared import CTkTooltip

class StatusBarWidget(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", height=48, **kwargs)
        self.pack_propagate(False)
        self.root_app = self.winfo_toplevel()

        # Subtle top border line
        self.border_line = ctk.CTkFrame(self, height=1, fg_color=get_color("colors.border.subtle"))
        self.border_line.pack(fill="x", side="top")

        # Action Log Row
        self.action_row = ctk.CTkFrame(self, fg_color="transparent")
        self.action_row.pack(fill="x", padx=8, pady=(8, 0))

        # Status text log
        self.lbl_action = ctk.CTkLabel(
            self.action_row, text="Waiting for client...",
            font=get_font("caption"),
            text_color=get_color("colors.text.muted"),
            wraplength=200, anchor="w"
        )
        self.lbl_action.pack(side="left", fill="x", expand=True)

        # Clear log button
        self.btn_clear_log = ctk.CTkButton(
            self.action_row, text="✕", width=18, height=18,
            corner_radius=9, font=get_font("caption"),
            fg_color="transparent",
            text_color=get_color("colors.text.disabled"),
            hover_color=get_color("colors.state.hover"),
            command=self._clear_action_log, cursor="hand2"
        )
        self.btn_clear_log.pack(side="right", padx=(4, 0))
        CTkTooltip(self.btn_clear_log, "Clear Log")

    def update_action_log(self, text: str):
        """Update the status bar text message safely on the main thread."""
        def _update():
            if self.winfo_exists():
                self.lbl_action.configure(text=text)
        if hasattr(self, 'root_app') and self.root_app:
            self.root_app.after(0, _update)
        else:
            # Fallback to winfo_toplevel if not initialized
            try:
                toplevel = self.winfo_toplevel()
                toplevel.after(0, _update)
            except Exception:
                pass

    def _clear_action_log(self):
        """Clear log text back to default waiting state."""
        self.update_action_log("Waiting for client...")
