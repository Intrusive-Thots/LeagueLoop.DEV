"""Tooltip component."""
from utils.logger import Logger
import tkinter
import customtkinter as ctk
from ..components.factory import get_color, get_font, TOKENS

class CTkTooltip:
    """
    Custom Tooltip for CTk Widgets.
    Uses standard tkinter.Toplevel to avoid icon glitches with CTk Toplevels.
    Features Malcolm's 'Holographic' slide-up animation and appearance delay.
    """
    def __init__(self, widget, text, delay=350):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip = None
        self._show_job = None
        self._target_y = 0
        self._current_y = 0
        self._x = 0

        self.widget.bind("<Enter>", self.schedule_show, add="+")
        self.widget.bind("<Leave>", self.hide, add="+")

    def schedule_show(self, event=None):
        """Schedule the tooltip to show after a delay."""
        self.cancel_job()
        self._show_job = self.widget.after(self.delay, self.show)

    def cancel_job(self):
        """Cancel any pending show jobs."""
        if self._show_job:
            self.widget.after_cancel(self._show_job)
            self._show_job = None

    def show(self, event=None):
        """Show the tooltip with a holographic slide-up effect."""
        try:
            # Re-calculate position in case widget moved
            if not getattr(self.widget, "winfo_exists", lambda: False)():
                return

            self._x = self.widget.winfo_rootx() + 25
            self._target_y = self.widget.winfo_rooty() + 25

            # Start slightly lower for the slide-up animation
            self._current_y = self._target_y + 10

            self.tooltip = tkinter.Toplevel(self.widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{self._x}+{self._current_y}")
            self.tooltip.configure(bg=get_color("colors.background.card", "#1E2328"))

            # Force it to stay on top
            self.tooltip.attributes("-topmost", True)

            frame = ctk.CTkFrame(
                self.tooltip,
                corner_radius=TOKENS.get("radius.sm"),
                fg_color=get_color("colors.background.card", "#1E2328"),
                border_color=get_color("colors.accent.gold", "#C8AA6E"),
                border_width=1,
            )
            frame.pack()

            label = ctk.CTkLabel(
                frame,
                text=self.text,
                bg_color="transparent",
                text_color=get_color("colors.text.primary"),
                padx=10,
                pady=5,
                font=get_font("body"),
            )
            label.pack()

            # Start animation
            self.animate_in()

        except Exception as e:  # pylint: disable=broad-exception-caught
            Logger.error("tooltip.py", f"Tooltip Error: {e}")

    def configure(self, text=None, delay=None):
        if text is not None:
            self.text = text
        if delay is not None:
            self.delay = delay

    def animate_in(self):
        """Holographic slide-up animation."""
        try:
            if not self.tooltip or not getattr(self.tooltip, "winfo_exists", lambda: False)():
                return

            if self._current_y > self._target_y:
                self._current_y -= max(1, (self._current_y - self._target_y) // 2)
                self.tooltip.wm_geometry(f"+{self._x}+{self._current_y}")
                self.widget.after(16, self.animate_in)
            else:
                self.tooltip.wm_geometry(f"+{self._x}+{self._target_y}")
        except Exception as e:
            Logger.error("tooltip.py", f"Tooltip Animation Error: {e}")

    def hide(self, event=None):
        """Hide the tooltip."""
        self.cancel_job()
        if self.tooltip:
            try:
                # CTk widgets inside Toplevels will crash if destroyed during an event loop.
                # Withdraw first to hide immediately, then safely request teardown.
                tw = self.tooltip
                self.tooltip = None
                tw.withdraw()
                tw.after(50, tw.destroy)
            except Exception as e:  # pylint: disable=broad-exception-caught
                Logger.error("tooltip.py", f"Handled exception: {e}")
            self.tooltip = None
