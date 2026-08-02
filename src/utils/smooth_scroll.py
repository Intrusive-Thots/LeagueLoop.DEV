"""
Smooth Scroll Enhancement
─────────────────────────
Adds momentum-based smooth scrolling to CTkScrollableFrame widgets.
Replaces the default jarring 3-line scroll with inertia-based easing.
"""

import customtkinter as ctk


def apply_smooth_scroll(scrollable_frame: ctk.CTkScrollableFrame, speed: float = 0.02, decay: float = 0.85):
    """
    Enhance a CTkScrollableFrame with momentum-based smooth scrolling.

    Parameters
    ----------
    scrollable_frame : ctk.CTkScrollableFrame
        The scrollable frame to enhance.
    speed : float
        Scroll speed multiplier per mouse wheel tick. Lower = smoother.
    decay : float
        Momentum decay factor per animation frame (0-1). Higher = more momentum.
    """
    state = {
        "velocity": 0.0,
        "animating": False,
    }

    def _on_mousewheel(event):
        """Capture scroll input and add to velocity."""
        # Windows sends delta in multiples of 120
        delta = -event.delta / 120.0
        state["velocity"] += delta * speed

        if not state["animating"]:
            state["animating"] = True
            _animate_scroll()

    def _animate_scroll():
        """Frame-by-frame scroll animation with momentum decay."""
        velocity = state["velocity"]

        if abs(velocity) < 0.001:
            state["velocity"] = 0.0
            state["animating"] = False
            return

        try:
            # Get the canvas from the scrollable frame
            canvas = scrollable_frame._parent_canvas
            if canvas.winfo_exists():
                canvas.yview_scroll(int(velocity * 100), "units") if abs(velocity) > 0.01 else None
                # Move by fractional amount for smooth feel
                current = canvas.yview()
                new_pos = current[0] + velocity
                new_pos = max(0.0, min(1.0, new_pos))
                canvas.yview_moveto(new_pos)
        except Exception:
            state["animating"] = False
            return

        # Apply decay
        state["velocity"] *= decay

        # Schedule next frame (~16ms for 60fps)
        try:
            scrollable_frame.after(16, _animate_scroll)
        except Exception:
            state["animating"] = False

    # Bind mousewheel to the scrollable frame and its children
    def _bind_recursive(widget):
        widget.bind("<MouseWheel>", _on_mousewheel, add="+")
        for child in widget.winfo_children():
            _bind_recursive(child)

    _bind_recursive(scrollable_frame)

    # Store reference to allow re-binding after content changes
    scrollable_frame._smooth_scroll_bind = _bind_recursive
    scrollable_frame._smooth_scroll_state = state
