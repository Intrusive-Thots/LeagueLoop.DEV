import tkinter as tk
from ui.components.factory import get_color
from utils.logger import Logger

class LolToggle(tk.Canvas):
    """Custom Riot-style animated sliding toggle switch using pure Canvas for maximum fidelity."""
    def __init__(self, master, width=32, height=16, variable=None, command=None, bg_color=None, **kwargs):
        # Palette: Enable keyboard focus by default for accessibility
        if bg_color is None:
            bg_color = get_color("colors.background.app", "#0A1428")
        kwargs.setdefault("takefocus", 1)
        super().__init__(master, width=width, height=height, highlightthickness=0, bg=bg_color, **kwargs)
        self.variable = variable
        self.command = command
        self._state = False
        if self.variable:
            self._state = self.variable.get()
            try:
                self.variable.trace_add("write", self._on_var_changed)
            except Exception as exc:
                Logger.debug("LolToggle", "__init__ suppressed an error", exc=exc)

        self.color_inactive = get_color("colors.background.card", "#1E2328")
        self.color_active = "#A88A4E" # C8AA6E dimmed
        self.color_knob = get_color("colors.text.primary", "#F0E6D2")
        self.color_focus_ring = get_color("colors.accent.gold", "#C8AA6E")

        self.pos_off = 2
        self.pos_on = 18 # 32 - 12 - 2
        self._current_x = self.pos_on if self._state else self.pos_off
        self._focused = False
        
        self.bind("<Button-1>", self.toggle)
        self.bind("<Enter>", lambda e: self.configure(cursor="hand2"))
        self.bind("<Leave>", lambda e: self.configure(cursor=""))
        
        # Palette: Keyboard accessibility bindings
        self.bind("<KeyPress-space>", self.toggle)
        self.bind("<Return>", self.toggle)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

        self._draw()

    def _on_focus_in(self, event=None):
        self._focused = True
        self._draw()

    def _on_focus_out(self, event=None):
        self._focused = False
        self._draw()

    def _draw(self):
        self.delete("all")
        bg_col = self.color_active if self._state else self.color_inactive
        
        # Track (Pill shape)
        # Palette: Show focus ring when active
        outline_col = self.color_focus_ring if self._focused else bg_col

        self.create_oval(0, 0, 16, 16, fill=bg_col, outline=outline_col, tags="track")
        self.create_oval(16, 0, 32, 16, fill=bg_col, outline=outline_col, tags="track")
        # Keep center rectangle outline same as fill to avoid vertical lines
        self.create_rectangle(8, 0, 24, 16, fill=bg_col, outline=bg_col, tags="track")
        
        if self._focused:
            self.create_line(8, 0, 24, 0, fill=outline_col, tags="track")
            self.create_line(8, 16, 24, 16, fill=outline_col, tags="track")

        # Knob
        k_y = 2
        k_s = 12
        x = self._current_x
        self.knob_id = self.create_oval(x, k_y, x+k_s, k_y+k_s, fill=self.color_knob, outline=self.color_knob)

    def _on_var_changed(self, *args):
        if not self.winfo_exists() or not self.variable:
            return
        new_val = bool(self.variable.get())
        if self._state != new_val:
            self._state = new_val
            self._animate()

    def toggle(self, event=None):
        self._state = not self._state
        if self.variable:
            self.variable.set(self._state)
            
        if self.command:
            self.command()
            
        self._animate()

    def _animate(self):
        target_x = self.pos_on if self._state else self.pos_off
        
        bg_col = self.color_active if self._state else self.color_inactive
        self.itemconfig("track", fill=bg_col, outline=bg_col)
        
        # Haptic visual pop
        self.itemconfig(self.knob_id, fill=self.color_focus_ring, outline=self.color_focus_ring)
        
        def step_animation():
            if not self.winfo_exists(): return
            diff = target_x - self._current_x
            
            if abs(diff) < 0.5:
                self._current_x = target_x
                self.coords(self.knob_id, self._current_x, 2, self._current_x + 12, 14)
                # Revert knob color
                self.itemconfig(self.knob_id, fill=self.color_knob, outline=self.color_knob)
                return
                
            self._current_x += diff * 0.3
            self.coords(self.knob_id, self._current_x, 2, self._current_x + 12, 14)
            self._anim_job = self.after(8, step_animation)
            
        step_animation()

    def destroy(self):
        if getattr(self, "_anim_job", None) is not None:
            try:
                self.after_cancel(self._anim_job)
                self._anim_job = None
            except Exception as exc:
                Logger.debug("LolToggle", "destroy suppressed an error", exc=exc)
        super().destroy()


