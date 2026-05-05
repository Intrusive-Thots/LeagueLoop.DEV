"""
New UI Component Factory using Design Tokens.
Centralizes the creation of styled widgets (Panels, Cards, Buttons) ensuring visual consistency.
"""
from utils.logger import Logger
import functools
import customtkinter as ctk
from ..theme.token_loader import TOKENS
from .hover import apply_hover_brightness, apply_press_effect

# ... (omitted)

# --- Token Parsing Helpers ---

@functools.lru_cache(maxsize=256)
def get_color(path, default="#000000"):
    """Retrieve color from tokens."""
    return TOKENS.get(*path.split("."), default=default)

@functools.lru_cache(maxsize=32)
def get_radius(size="md"):
    """Retrieve corner radius."""
    return TOKENS.get("radius", size, default=10)

@functools.lru_cache(maxsize=32)
def get_font(type="body", weight=None):
    """Retrieve font tuple. Weight can be 'bold', 'medium', or 'normal'.
    
    Font chain: Beaufort for LOL > Cinzel > Segoe UI (headers)
                Spiegel > Inter > Segoe UI (body/caption)
    On this system only Segoe UI is available.
    """
    # Headers: larger, bolder
    if type == "header" or type == "title":
        family = "Beaufort for LOL"
        size = 14 if type == "header" else 15
        weight_val = "bold"
    elif type == "section":
        # Section headers inside cards (e.g. "LOBBY & QUEUE")
        family = "Segoe UI"
        size = 11
        weight_val = "bold"
    elif type == "caption":
        family = "Segoe UI"
        size = 11
        weight_val = "normal"
    elif type == "small":
        family = "Segoe UI"
        size = 10
        weight_val = "normal"
    else:  # body
        family = "Segoe UI"
        size = 12
        weight_val = "normal"
    
    if weight:
        weight_val = "normal" if weight == "medium" else weight
        
    return (family, size, weight_val)

@functools.lru_cache(maxsize=32)
def parse_border(token_key):
    """
    Parse a border token like '1px solid #RRGGBB'.
    Returns (width, color).
    """
    val = TOKENS.get("borders", token_key)
    if not val:
        return 0, None
    
    parts = val.split()
    try:
        width = int(parts[0].replace("px", ""))
        color = parts[2]
        if "rgba" in color:
             return width, "#3A4654" 
        return width, color
    except Exception as e:
        Logger.error("factory.py", f"Handled exception: {e}")
        return 0, None

# --- Components ---

class RiotButton(ctk.CTkFrame):
    """Custom button emulating Riot's 2-layer depth with top highlight."""
    def __init__(self, master, text, style="primary", width=120, height=30, command=None, font=None, **kwargs):
        # Extract text styling
        text_color = kwargs.pop("text_color", None)
        
        if style == "primary" or style == "success":
            outer_color = get_color("colors.accent.gold", "#C8AA6E")
            inner_color = "#A98A48"
            hover_color = get_color("colors.accent.gold", "#C8AA6E")  # Brighten on hover
            base_text_color = text_color or get_color("colors.background.app", "#091428")
        elif style == "ghost" or style == "danger":
            outer_color = get_color("colors.background.card", "#1E2328") if style == "danger" else "transparent"
            inner_color = "transparent"
            hover_color = "#1C2630" if style == "ghost" else get_color("colors.state.danger.muted", "#4d1111")
            base_text_color = text_color or (get_color("colors.state.danger", "#E74C3C") if style == "danger" else get_color("colors.text.primary", "#F0E6D2"))
        else: # secondary
            outer_color = get_color("colors.background.card", "#1E2328")
            inner_color = get_color("colors.background.app", "#0A1428")
            hover_color = get_color("colors.background.card", "#1E2328")
            base_text_color = text_color or get_color("colors.accent.gold", "#C8AA6E")

        super().__init__(master, width=width, height=height, fg_color=outer_color, corner_radius=2, **kwargs)
        self.pack_propagate(False)
        self.command = command
        
        padding = 1 if style not in ("ghost",) else 0
        self.inner = ctk.CTkFrame(self, fg_color=inner_color, corner_radius=1)
        self.inner.pack(fill="both", expand=True, padx=padding, pady=padding)
        
        if style == "primary":
            self.highlight = ctk.CTkFrame(self.inner, height=1, fg_color="#D3B679", corner_radius=0)
            self.highlight.pack(fill="x", side="top")
            
        btn_font = font or get_font("body", "bold")
        self.lbl = ctk.CTkLabel(self.inner, text=text, font=btn_font, text_color=base_text_color)
        self.lbl.pack(expand=True)
        
        self.configure(cursor="hand2")
        self.inner.configure(cursor="hand2")
        self.lbl.configure(cursor="hand2")

        for w in (self, self.inner, self.lbl):
            w.bind("<Enter>", lambda e: self._on_enter(hover_color))
            w.bind("<Leave>", lambda e: self._on_leave(inner_color))
            w.bind("<Button-1>", self._on_click)
            
        # 🎨 Palette: Enable keyboard accessibility for custom canvas buttons
        if hasattr(self, "_canvas"):
            self._canvas.configure(takefocus=1)
            self._canvas.bind("<FocusIn>", lambda e: self._on_enter(hover_color))
            self._canvas.bind("<FocusOut>", lambda e: self._on_leave(inner_color))

            # Bind to all relevant widget components to ensure events aren't swallowed
            for w in (self, self.inner, self.lbl, self._canvas):
                w.bind("<KeyPress-space>", lambda e: self._on_click(e))
                w.bind("<space>", lambda e: self._on_click(e))
                w.bind("<Return>", lambda e: self._on_click(e))

        self._inner_color = inner_color
        self._disabled = False  # Item #194: Track disabled state
        
    def _on_enter(self, h_color):
        if self._disabled:
            return
        self.configure()
        self.inner.configure(fg_color=h_color)
        
    def _on_leave(self, i_color):
        self.configure()
        self.inner.configure(fg_color=i_color)
        
    def _on_click(self, e):
        if self._disabled:
            return
        # Optional: Add small press scale if desired
        if hasattr(self, "_canvas"):
            self._canvas.focus_set()
        if self.command:
            self.command()

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.lbl.configure(text=kwargs.pop("text"))
        if "text_color" in kwargs:
            self.lbl.configure(text_color=kwargs.pop("text_color"))
        if "inner_color" in kwargs:
            inner_c = kwargs.pop("inner_color")
            self.inner.configure(fg_color=inner_c)
            self._inner_color = inner_c
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        # Item #194: Support disabled state
        if "state" in kwargs:
            state = kwargs.pop("state")
            if state == "disabled":
                self._disabled = True
                self.lbl.configure(text_color=get_color("colors.text.disabled"))
                self.inner.configure(fg_color=get_color("colors.background.card"))
                for w in (self, self.inner, self.lbl):
                    w.configure(cursor="")
            else:
                self._disabled = False
                self.lbl.configure(text_color=self.lbl.cget("text_color"))
                self.inner.configure(fg_color=self._inner_color)
                for w in (self, self.inner, self.lbl):
                    w.configure(cursor="hand2")
        if kwargs:
            super().configure(**kwargs)

def make_button(parent, text, style="primary", width=None, command=None, icon=None, **kw):
    """Factory wrapper for new RiotButton."""
    w = kw.pop("width", width or 120)
    h = kw.pop("height", 30)
    kw.pop("cursor", None)
    if "variant" in kw:
        style = kw.pop("variant")
    return RiotButton(parent, text=text, style=style, width=w, height=h, command=command, **kw)


def make_input(parent, placeholder="", width=None, **kw):
    """
    Create a standardized input field.
    """
    w = kw.pop("width", width or 200)
    font = kw.pop("font", get_font("body"))
    radius = kw.pop("corner_radius", get_radius("sm"))
    height = kw.pop("height", 32)
    
    bg_color = kw.pop("fg_color", get_color("colors.background.app"))
    def_border_w, def_border_c = parse_border("subtle")
    border_w = kw.pop("border_width", def_border_w)
    border_c = kw.pop("border_color", def_border_c)
    kw.pop("cursor", None)
    
    entry = ctk.CTkEntry(
        parent,
        width=w,
        height=height,
        corner_radius=radius,
        font=font,
        fg_color=bg_color, 
        border_color=border_c,
        border_width=border_w,
        placeholder_text=placeholder,
        placeholder_text_color=get_color("colors.text.muted"),
        text_color=get_color("colors.text.primary"),
        
        **kw
    )

    # ⚡ Bolt: Precompute static colors for focus handlers to avoid main thread latency
    # during high-frequency focus events.
    _focus_border = get_color("colors.accent.blue")
    _focus_bg = get_color("colors.background.card")
    _unfocus_border = border_c
    _unfocus_bg = bg_color

    def _on_focus(e):
        entry.configure(
            border_color=_focus_border,
            fg_color=_focus_bg
        )

    def _on_unfocus(e):
        entry.configure(
            border_color=_unfocus_border,
            fg_color=_unfocus_bg
        )

    entry.bind("<FocusIn>", _on_focus, add="+")
    entry.bind("<FocusOut>", _on_unfocus, add="+")

    return entry


def make_card(parent, title=None, fg_color=None, border_color=None, corner_radius=None,
              padx=10, pady=10, inner_padx=10, inner_pady=8, collapsible=False, start_collapsed=False):
    """Create a standardized League-styled card frame.
    
    Returns the content frame (inside the card) where widgets should be packed.
    If title is provided, a gold header label and divider are automatically added.
    
    Args:
        parent: Parent widget
        title: Optional gold header text (e.g. "LOBBY & QUEUE")
        fg_color: Card background. Defaults to token card color.
        border_color: Card border color. Defaults to token card border.
        corner_radius: Corner radius. Defaults to token md radius.
        padx/pady: External padding when packing the card
        inner_padx/inner_pady: Internal content padding
        collapsible: If True, title becomes a clickable toggle with smooth animation
        start_collapsed: If True and collapsible is True, starts in collapsed state
    
    Returns:
        content_frame: CTkFrame where child widgets should be packed
    """
    card_bg = fg_color or get_color("colors.background.card", "#0F1923")
    card_border_w, card_border_c = parse_border("card")
    border_c = border_color or card_border_c or "#1A2332"
    radius = corner_radius or get_radius("md")
    
    card = ctk.CTkFrame(
        parent,
        fg_color=card_bg,
        corner_radius=radius,
        border_width=1,
        border_color=border_c
    )
    card.pack(fill="x", padx=padx, pady=pady)
    
    # Optional hover effect on the entire card
    _hover_bg = get_color("colors.background.card_hover", "#132030")
    card.bind("<Enter>", lambda e: card.configure(fg_color=_hover_bg))
    card.bind("<Leave>", lambda e: card.configure(fg_color=card_bg))
    
    header_frame = None
    chevron = None
    divider = None
    
    if title:
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=inner_padx, pady=(inner_pady, 2))
        
        chevron_text = "▼  " if not (collapsible and start_collapsed) else "▶  "
        if collapsible:
            chevron = ctk.CTkLabel(
                header_frame, text=chevron_text,
                font=get_font("caption", "bold"),
                text_color=get_color("colors.text.muted")
            )
            chevron.pack(side="left")
            
        title_label = ctk.CTkLabel(
            header_frame, text=title,
            font=get_font("section", "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            anchor="w"
        )
        title_label.pack(side="left", fill="x")
        
        # Gold-tinted divider
        divider = ctk.CTkFrame(
            card, height=1,
            fg_color=get_color("colors.border.subtle", "#1E2328")
        )
        if not (collapsible and start_collapsed):
            divider.pack(fill="x", padx=inner_padx, pady=(0, inner_pady - 2))
    
    # Wrapper frame for animation purposes
    content_wrapper = ctk.CTkFrame(card, fg_color="transparent")
    if not (title and collapsible and start_collapsed):
        content_wrapper.pack(fill="x", padx=inner_padx, pady=(0 if title else inner_pady, inner_pady))
    
    content = ctk.CTkFrame(content_wrapper, fg_color="transparent")
    content.pack(fill="both", expand=True)
    
    # Store reference to outer card and header on content frame for external access
    content._card = card
    content._header = header_frame
    
    if title and collapsible:
        class AnimatedToggle:
            def __init__(self):
                self.is_expanded = not start_collapsed
                self.animating = False
                self.current_h = 0
                self.target_h = 0
                
                # Bind clicks
                header_frame.configure(cursor="hand2")
                header_frame.bind("<Button-1>", self.toggle)
                for child in header_frame.winfo_children():
                    child.configure(cursor="hand2")
                    child.bind("<Button-1>", self.toggle)
                    
            def toggle(self, event=None):
                if self.animating: return
                self.animating = True
                
                if self.is_expanded:
                    chevron.configure(text="▶  ")
                    self.target_h = 0
                    self.current_h = content.winfo_reqheight()
                    content_wrapper.configure(height=self.current_h)
                    content_wrapper.pack_propagate(False)
                    self.animate_collapse()
                else:
                    chevron.configure(text="▼  ")
                    content_wrapper.pack(fill="x", padx=inner_padx, pady=(0 if title else inner_pady, inner_pady))
                    divider.pack(fill="x", padx=inner_padx, pady=(0, inner_pady - 2), before=content_wrapper)
                    
                    # Temporarily allow propagation to calculate required height
                    content_wrapper.pack_propagate(True)
                    content_wrapper.update_idletasks()
                    self.target_h = content.winfo_reqheight()
                    
                    self.current_h = 0
                    content_wrapper.configure(height=0)
                    content_wrapper.pack_propagate(False)
                    self.animate_expand()
                    
            def animate_collapse(self):
                step = max(4, self.current_h * 0.25)
                self.current_h -= step
                if self.current_h <= 0:
                    content_wrapper.pack_forget()
                    divider.pack_forget()
                    self.is_expanded = False
                    self.animating = False
                else:
                    content_wrapper.configure(height=int(self.current_h))
                    card.after(16, self.animate_collapse)

            def animate_expand(self):
                step = max(4, (self.target_h - self.current_h) * 0.25)
                self.current_h += step
                if self.current_h >= self.target_h - 2:
                    content_wrapper.configure(height=self.target_h)
                    content_wrapper.pack_propagate(True)
                    self.is_expanded = True
                    self.animating = False
                else:
                    content_wrapper.configure(height=int(self.current_h))
                    card.after(16, self.animate_expand)
                    
        content._toggle_controller = AnimatedToggle()
    
    return content

def make_divider(parent, padx=0, pady=0, side="top"):
    """Create a standardized 1px horizontal divider."""
    divider = ctk.CTkFrame(
        parent, height=1,
        fg_color=get_color("colors.border.subtle", "#1E2328")
    )
    divider.pack(fill="x", side=side, padx=padx, pady=pady)
    return divider
