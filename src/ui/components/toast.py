"""
Holographic Toasts - Delightful Notification System
Provides non-intrusive, animated feedback for background actions.
"""
from utils.logger import Logger
import customtkinter as ctk
from .factory import get_color, get_font, get_radius, parse_border
from .color_utils import lighten_color

class Toast(ctk.CTkFrame):
    """
    A single toast notification.
    Designed with a 'Holographic' aesthetic: translucent bg, subtle glow, and clean typography.
    """
    def __init__(self, parent, message, icon="✨", duration=3000, theme="primary", confetti=False):
        # Resolve colors based on theme
        """Initializes the Toast component."""
        bg_hex = get_color("colors.background.panel")
        
        border_w, border_c = parse_border("subtle")
        if theme == "success":
            border_c = get_color("colors.state.success")
        elif theme == "error":
            border_c = get_color("colors.state.danger")

        super().__init__(
            parent,
            fg_color=bg_hex,
            corner_radius=get_radius("md"),
            border_width=1,
            border_color=border_c,
            cursor="hand2"
        )
        
        self.duration = duration
        self._is_dismissing = False
        self._original_bg = bg_hex  # Stash for hover restore

        # Malcolm's UX Enhancement: Add subtle hover effect for interactive feel
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self.dismiss)

        # Layout
        self.grid_columnconfigure(1, weight=1)
        
        # Icon
        self.lbl_icon = ctk.CTkLabel(
            self, text=icon, font=get_font("body"), width=30, cursor="hand2"
        )
        self.lbl_icon.grid(row=0, column=0, padx=(10, 5), pady=10)
        self.lbl_icon.bind("<Button-1>", self.dismiss)

        # Message
        self.lbl_msg = ctk.CTkLabel(
            self, text=message, font=get_font("body", "medium"),
            text_color=get_color("colors.text.primary"),
            anchor="w", justify="left", wraplength=250, cursor="hand2"
        )
        self.lbl_msg.grid(row=0, column=1, padx=(5, 15), pady=10)
        self.lbl_msg.bind("<Button-1>", self.dismiss)

        # Slide-in Animation State
        self._target_y = 5 # Padding target
        self._current_y = 50

        # Confetti state
        self.confetti = confetti
        self._particles = []
        self._confetti_job = None

        # Start dismissal timer
        self.after(self.duration, self.dismiss)

        # Cleanup on destroy
        self.bind("<Destroy>", lambda e: self._cleanup_confetti() if getattr(e, "widget", None) == self else None, add="+")

    def _spawn_confetti(self):
        """Malcolm's Infusion: Spawns delightful confetti particles across the top-level window."""
        try:
            import random
            top = self.master.master
            if not top: return

            # Get window dimensions
            w = top.winfo_width()
            h = top.winfo_height()

            # Start position: bottom-right (where toasts appear)
            start_x = int(w * 0.9)
            start_y = int(h * 0.9)

            colors = [
                get_color("colors.accent.primary"),
                get_color("colors.accent.gold"),
                get_color("colors.state.success"),
                get_color("colors.accent.purple")
            ]

            # Spawn 20-30 particles
            for _ in range(random.randint(20, 30)):
                size = random.randint(4, 8)
                p = ctk.CTkFrame(
                    top,
                    width=size, height=size,
                    corner_radius=size // 2, # Circular confetti
                    fg_color=random.choice(colors)
                )

                # Physics properties
                dx = random.uniform(-15, 5)  # Shoot leftwards and outwards
                dy = random.uniform(-20, -5) # Shoot upwards

                p.place(x=start_x, y=start_y)
                self._particles.append({"widget": p, "x": start_x, "y": start_y, "dx": dx, "dy": dy, "life": random.randint(30, 60)})

            self._animate_confetti()
        except Exception as e:
            Logger.error("toast.py", f"Confetti error: {e}")

    def _animate_confetti(self):
        """Physics loop for confetti."""
        if not self.winfo_exists() or not self._particles:
            return

        alive_particles = []
        for p in self._particles:
            widget = p["widget"]
            if not getattr(widget, "winfo_exists", lambda: False)():
                continue

            p["life"] -= 1
            if p["life"] <= 0:
                widget.destroy()
                continue

            # Gravity and friction
            p["dy"] += 1.0  # Gravity
            p["dx"] *= 0.95 # Air resistance

            p["x"] += p["dx"]
            p["y"] += p["dy"]

            try:
                widget.place(x=int(p["x"]), y=int(p["y"]))
                alive_particles.append(p)
            except Exception:
                widget.destroy()

        self._particles = alive_particles

        if self._particles:
            self._confetti_job = self.after(20, self._animate_confetti)

    def animate_in(self):
        """Slide in animation for holographic feel."""
        if not self.winfo_exists():
            return
        if self._current_y > self._target_y:
            self._current_y = max(self._target_y, self._current_y - 8)
            # Use pack_configure to adjust padding dynamically
            self.pack_configure(pady=(self._current_y, 0))
            self.after(16, self.animate_in)
        else:
            self.pack_configure(pady=(self._target_y, 0))
            if self.confetti:
                self._spawn_confetti()

    def _on_hover(self, event=None):
        try:
            bg = self.cget("fg_color")
            self._original_bg = bg
            self.configure(fg_color=lighten_color(bg, 0.2))
        except Exception as e:
            Logger.error("toast.py", f"Handled exception: {e}")

    def _on_leave(self, event=None):
        try:
            # Restore the original background, not always the panel color
            self.configure(fg_color=self._original_bg)
        except Exception as e:
            Logger.error("toast.py", f"Handled exception: {e}")

    def dismiss(self, event=None):
        """Start the dismissal animation."""
        if self._is_dismissing:
            return
        self._is_dismissing = True
        self._slide_out()

    def _slide_out(self):
        """Slide out animation before destroying."""
        if not self.winfo_exists():
            return
        if self._current_y < 50:
            self._current_y += 8
            self.pack_configure(pady=(self._current_y, 0))
            self.after(16, self._slide_out)
        else:
            self._cleanup_confetti()
            self.destroy()

    def _cleanup_confetti(self):
        if self._confetti_job:
            self.after_cancel(self._confetti_job)
            self._confetti_job = None
        for p in self._particles:
            try:
                if getattr(p["widget"], "winfo_exists", lambda: False)():
                    p["widget"].destroy()
            except Exception:
                pass
        self._particles.clear()

class ToastManager:
    """
    Manages the lifecycle and positioning of toasts.
    """
    _instance = None
    MAX_TOASTS = 5  # Item #189: Prevent unbounded toast accumulation

    @classmethod
    def get_instance(cls, root=None):
        """Gets or creates the singleton ToastManager instance."""
        if cls._instance is None:
            if root is None:
                raise ValueError("ToastManager requires a root window for initialization.")
            cls._instance = cls(root)
        return cls._instance

    def __init__(self, root):
        """Initializes the ToastManager component."""
        self.root = root
        self._toasts = []  # Item #184: Instance-level list, not class-level
        self.container = ctk.CTkFrame(self.root, fg_color="transparent")
        # Position at bottom-right
        self.container.place(relx=0.98, rely=0.95, anchor="se")
        
    def show(self, message, icon="✨", duration=3000, theme="primary", confetti=False):
        """Create and show a toast."""
        # Item #189: Evict oldest toast if at capacity
        while len(self._toasts) >= self.MAX_TOASTS:
            oldest = self._toasts[0]
            try:
                oldest.dismiss()
            except Exception:
                pass
            if oldest in self._toasts:
                self._toasts.remove(oldest)

        toast = Toast(self.container, message, icon, duration, theme, confetti)
        # Pack with initial high padding for animation
        toast.pack(pady=(50, 0), fill="x")
        self._toasts.append(toast)
        
        # Trigger entry animation
        toast.animate_in()

        # Cleanup reference when destroyed
        def on_destroy(e):
            """Handles destruction."""
            if toast in self._toasts:
                self._toasts.remove(toast)
        
        toast.bind("<Destroy>", on_destroy)

