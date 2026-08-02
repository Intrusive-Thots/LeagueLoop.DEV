"""Hover animation utilities."""
from utils.logger import Logger
from .color_utils import lighten_color, darken_color


def apply_hover_brightness(widget, normal_color, boost_percent=8):
    """Simple hover brightness boost for any CTk widget with fg_color."""
    hover_color = lighten_color(normal_color, boost_percent)

    def on_enter(_):
        try:
            widget.configure(fg_color=hover_color)
        except Exception as e:  # pylint: disable=broad-exception-caught
            Logger.error("hover.py", f"Handled exception: {e}")

    def on_leave(_):
        try:
            widget.configure(fg_color=normal_color)
        except Exception as e:  # pylint: disable=broad-exception-caught
            Logger.error("hover.py", f"Handled exception: {e}")

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


def apply_click_animation(widget, normal_color, pulse_color=None, button_num=1):
    """
    🔮 Malcolm's Infusion: Global Click Pulse
    Applies a momentary gamified 'pulse' color flash to a widget upon clicking.
    Provides immediate haptic-like visual feedback that feels highly responsive.
    """
    # lighten_color and Logger are already imported at module level

    # Precompute the pulse color outside the event handler to avoid redundant
    # string parsing and math operations on every single click event.
    _precomputed_pulse = None
    if pulse_color:
        _precomputed_pulse = pulse_color
    elif normal_color == "transparent":
        _precomputed_pulse = "#C8A45D"
    else:
        _precomputed_pulse = lighten_color(normal_color, 35)

    def on_click(_):
        try:
            # Skip if widget is disabled
            if hasattr(widget, "cget") and widget.cget("state") == "disabled":
                return

            # Prevent overlapping animations from corrupting base colors on rapid double-clicks
            if getattr(widget, "_is_pulsing", False):
                return
            widget._is_pulsing = True

            # Stash original colors securely
            if not hasattr(widget, "_orig_pulse_fg"):
                widget._orig_pulse_fg = widget.cget("fg_color")
            if not hasattr(widget, "_orig_pulse_hover"):
                widget._orig_pulse_hover = widget.cget("hover_color")

            orig_fg = widget._orig_pulse_fg
            orig_hover = widget._orig_pulse_hover

            # Determine active pulse color. We use the precomputed normal color pulse,
            # UNLESS the widget has a specific hover color we should base the pulse on
            # to maintain visual hierarchy.
            if pulse_color:
                active_pulse = pulse_color
            elif orig_hover and orig_hover != "transparent" and orig_hover != normal_color:
                # Extract first color if it's a tuple
                hover_base = orig_hover[0] if isinstance(orig_hover, tuple) else orig_hover
                active_pulse = lighten_color(hover_base, 35)
            else:
                active_pulse = _precomputed_pulse

            # CustomTkinter renders hover_color when the mouse is over the widget.
            # To show a pulse effect during a click, we must change both fg_color and hover_color.
            widget.configure(fg_color=active_pulse, hover_color=active_pulse)

            # Schedule reversion (feels like a quick satisfying snap)
            def _revert():
                if getattr(widget, "winfo_exists", lambda: False)():
                    widget.configure(fg_color=orig_fg, hover_color=orig_hover)
                    widget._is_pulsing = False

            if getattr(widget, "winfo_exists", lambda: False)():
                widget.after(150, _revert)
        except Exception as e:
            if hasattr(widget, "_is_pulsing"):
                widget._is_pulsing = False
            Logger.error("hover.py", f"Handled exception in click animation: {e}")

    # Add to ButtonPress-1 to align with press logic without removing existing handlers
    widget.bind(f"<ButtonPress-{button_num}>", on_click, add="+")

def apply_press_effect(widget, normal_color, press_color=None):
    """
    Bind press animation (click down/up).
    If press_color is None, it defaults to normal_color (no change) or could be calculated.
    For now, we will perform a slight darken if no press_color is provided.
    """
    # darken_color is already imported at module level
    
    active_color = press_color or darken_color(normal_color, 10)

    def on_press(_):
        try:
            widget.configure(fg_color=active_color)
        except Exception as e:
            Logger.error("hover.py", f"Handled exception: {e}")

    def on_release(_):
        try:
            # We assume the mouse is still hovering, so we might want to return to 
            # hover state if possible, but simplest is return to normal and let hover re-trigger
            # or rely on the hover handler to fix it on next move.
            # Ideally, we restore normal, then let hover take over.
            widget.configure(fg_color=normal_color)
            # If the mouse is still inside, the hover handler <Enter> won't trigger again 
            # automatically unless we move. 
            # A robust system would track state. For now, we revert to normal.
        except Exception as e:
            Logger.error("hover.py", f"Handled exception: {e}")

    widget.bind("<ButtonPress-1>", on_press, add="+")
    widget.bind("<ButtonRelease-1>", on_release, add="+")

# Cache tokens globally to avoid re-importing and re-parsing on every widget creation
_card_hover_border = None
_card_normal_border = None

def apply_card_hover(widget):
    global _card_hover_border, _card_normal_border
    if _card_hover_border is None:
        from ui.ui_shared import get_color
        from ui.components.factory import parse_border
        _card_hover_border = get_color("colors.accent.primary", default="#0AC8B9")
        _, _card_normal_border = parse_border("subtle")

    # ⚡ Bolt: Fast path static bindings using closure variables
    hb = _card_hover_border
    nb = _card_normal_border

    def on_enter(_):
        try:
            widget.configure(border_color=hb)
        except Exception as e:

            Logger.error("hover.py", f"Handled exception: {type(e).__name__}: {e}")

    def on_leave(_):
        try:
            widget.configure(border_color=nb)
        except Exception as e:

            Logger.error("hover.py", f"Handled exception: {type(e).__name__}: {e}")

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")


def apply_queue_pulse(widget, color_a="#C8AA6E", color_b="#A98A48", interval=800):
    """Pulse between two colors on a widget to indicate active queue state.
    
    Call stop_queue_pulse(widget) to stop the animation.
    
    Args:
        widget: CTkFrame or RiotButton to pulse
        color_a: First pulse color (bright)
        color_b: Second pulse color (dim)
        interval: Milliseconds per half-cycle
    """
    widget._pulse_active = True
    widget._pulse_phase = True  # True = color_a, False = color_b
    
    def _tick():
        if not getattr(widget, "_pulse_active", False):
            return
        if not widget.winfo_exists():
            return
        try:
            c = color_a if widget._pulse_phase else color_b
            # For RiotButton (CTkFrame with .inner), pulse the inner frame
            if hasattr(widget, "inner"):
                widget.inner.configure(fg_color=c)
            else:
                widget.configure(fg_color=c)
            widget._pulse_phase = not widget._pulse_phase
            widget.after(interval, _tick)
        except Exception as e:
            Logger.error("hover.py", f"Pulse animation error: {e}")
    
    _tick()


def stop_queue_pulse(widget, restore_color=None):
    """Stop a running queue pulse animation."""
    widget._pulse_active = False
    if restore_color and widget.winfo_exists():
        try:
            if hasattr(widget, "inner"):
                widget.inner.configure(fg_color=restore_color)
            else:
                widget.configure(fg_color=restore_color)
        except Exception:
            pass
