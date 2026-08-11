"""
Auto-Ban Priority List Editor — same UX as the ARAM list (icons + search).
Single custom title bar; stores champions in config auto_ban_list.
"""
import ctypes
import customtkinter as ctk

from ui.components.factory import get_color, get_font
from ui.components.priority_grid import PriorityIconGrid
from core.constants import SPACING_MD, SPACING_SM


def _get_league_client_rect():
    try:
        user32 = getattr(ctypes.windll, "user32", None)
        if not user32:
            return None
        league_hwnd = [0]
        riot_hwnd = [0]

        def enum_callback(h, extra):
            if not user32.IsWindowVisible(h):
                return True
            length = user32.GetWindowTextLengthW(h)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(h, buf, length + 1)
                title = buf.value.lower().strip()
                if title == "league of legends":
                    league_hwnd[0] = h
                    return False
                if title == "riot client" and riot_hwnd[0] == 0:
                    riot_hwnd[0] = h
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
        hwnd = league_hwnd[0] or riot_hwnd[0]
        if hwnd and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd):
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        pass
    return None


class BanListWindow(ctk.CTkToplevel):
    """Dedicated Auto-Ban champion list editor (icon grid + text search)."""

    _instance = None

    def __init__(self, master, config, assets, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.assets = assets

        self.title("Auto-Ban List")
        try:
            self.overrideredirect(True)
        except Exception:
            pass
        self.resizable(True, True)
        self.configure(fg_color=get_color("colors.accent.gold", "#C8AA6E"))

        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        self._build_ui()
        self._setup_dragging()
        self.after(50, self._set_initial_geometry)
        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _build_ui(self):
        self.outer_frame = ctk.CTkFrame(
            self,
            fg_color="#0A1428",
            border_width=2,
            border_color=get_color("colors.accent.gold", "#C8AA6E"),
            corner_radius=0,
        )
        self.outer_frame.pack(fill="both", expand=True)

        # Single title bar (no OS chrome)
        self.header = ctk.CTkFrame(
            self.outer_frame, fg_color="#121C2A", height=36, corner_radius=0
        )
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        ctk.CTkLabel(
            self.header,
            text="🚫  AUTO-BAN LIST",
            font=get_font("body", "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
        ).pack(side="left", padx=12)

        self.btn_done = ctk.CTkButton(
            self.header,
            text="Done",
            width=64,
            height=26,
            corner_radius=6,
            font=get_font("caption", "bold"),
            fg_color=get_color("colors.accent.gold", "#C8AA6E"),
            hover_color="#A88B4A",
            text_color="#0A1428",
            border_width=1,
            border_color="#E0C98A",
            command=self._on_close,
            cursor="hand2",
        )
        self.btn_done.pack(side="right", padx=(4, 8))

        self.btn_close = ctk.CTkButton(
            self.header,
            text="✕",
            width=28,
            height=26,
            corner_radius=4,
            font=get_font("body", "bold"),
            fg_color="transparent",
            text_color="#FF4655",
            hover_color="#3A1924",
            border_width=1,
            border_color="#5A2030",
            command=self._on_close,
            cursor="hand2",
        )
        self.btn_close.pack(side="right", padx=4)

        self.body_frame = ctk.CTkFrame(self.outer_frame, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        self.grid_widget = PriorityIconGrid(
            self.body_frame,
            self.config,
            self.assets,
            expanded=True,
            list_kind="ban",
            show_section_header=False,
        )
        self.grid_widget.pack(fill="both", expand=True)

        # Ban-specific options footer
        opts = ctk.CTkFrame(self.outer_frame, fg_color="#121C2A", height=44, corner_radius=0)
        opts.pack(fill="x", side="bottom")
        opts.pack_propagate(False)

        self._respect_hovers_var = ctk.BooleanVar(
            value=bool(self.config.get("auto_ban_respect_hovers", True))
        )
        sw = ctk.CTkSwitch(
            opts,
            text="Respect Teammate Hovers",
            font=get_font("caption", "bold"),
            variable=self._respect_hovers_var,
            progress_color=get_color("colors.accent.gold", "#C8AA6E"),
            command=self._on_respect_toggle,
        )
        sw.pack(side="left", padx=SPACING_MD, pady=SPACING_SM)

        ctk.CTkLabel(
            opts,
            text="Won't ban champs hovered by teammates",
            font=get_font("caption"),
            text_color=get_color("colors.text.muted"),
        ).pack(side="left", padx=(0, 8))

    def _on_respect_toggle(self):
        self.config.set("auto_ban_respect_hovers", bool(self._respect_hovers_var.get()))

    def _setup_dragging(self):
        self._drag_data = {"x": 0, "y": 0}
        self.header.bind("<ButtonPress-1>", self._on_drag_start)
        self.header.bind("<B1-Motion>", self._on_drag_motion)
        for child in self.header.winfo_children():
            if isinstance(child, ctk.CTkButton):
                continue
            child.bind("<ButtonPress-1>", self._on_drag_start)
            child.bind("<B1-Motion>", self._on_drag_motion)

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        x = self.winfo_x() - self._drag_data["x"] + event.x
        y = self.winfo_y() - self._drag_data["y"] + event.y
        self.geometry(f"+{x}+{y}")

    def _on_resize(self, event):
        if event.widget != self:
            return
        w = event.width
        if w > 100 and hasattr(self, "grid_widget"):
            self.grid_widget.set_icons_per_row(max(4, (w - 48) // 52))

    def _set_initial_geometry(self):
        w, h = 800, 520
        rect = _get_league_client_rect()
        if rect:
            cx, cy, cw, ch = rect
            x = cx + (cw - w) // 2
            y = cy + (ch - h) // 2
        else:
            try:
                mx = self.master.winfo_rootx()
                my = self.master.winfo_rooty()
                x = mx + 40
                y = my + 40
            except Exception:
                x, y = 200, 150
        if x < 0:
            x = 100
        if y < 0:
            y = 100
        try:
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _on_close(self):
        self.destroy()

    def destroy(self):
        BanListWindow._instance = None
        super().destroy()

    @classmethod
    def open_window(cls, master, config, assets):
        if cls._instance is not None and cls._instance.winfo_exists():
            cls._instance.lift()
            cls._instance.focus_force()
        else:
            cls._instance = cls(master, config, assets)
        return cls._instance
