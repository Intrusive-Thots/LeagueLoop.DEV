"""
ARAM Top Drawer Window — Sleek top drawer panel for managing the ARAM Champion Priority List.
Drops down from the top edge of the League of Legends client window.
Dynamic column count scales automatically based on the client's width.
"""
import ctypes
import threading
import time
import customtkinter as ctk
from ui.components.factory import get_color, get_font
from ui.components.priority_grid import PriorityIconGrid

_CLIENT_TITLES = {"league of legends", "riot client"}


def _get_league_client_rect():
    """Find position and dimensions of the League Client window (thread-safe)."""
    try:
        user32 = getattr(ctypes.windll, "user32", None)
        if not user32:
            return None

        target_hwnd = [0]
        def enum_callback(h, extra):
            if not user32.IsWindowVisible(h):
                return True
            length = user32.GetWindowTextLengthW(h)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(h, buf, length + 1)
                title = buf.value.lower().strip()
                if title in _CLIENT_TITLES:
                    target_hwnd[0] = h
                    return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
        hwnd = target_hwnd[0]

        if hwnd != 0 and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd):
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            cx, cy = rect.left, rect.top
            cw = rect.right - rect.left
            ch = rect.bottom - rect.top
            return (cx, cy, cw, ch)
    except Exception:
        pass
    return None


class AramListWindow(ctk.CTkToplevel):
    """Top-drawer overlay window attached to the top edge of the League Client."""

    _instance = None

    def __init__(self, master, config, assets, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.assets = assets
        self._tracking_active = True
        self._last_geo = None

        self.title("Queqq — ARAM Priority List Drawer")
        self.overrideredirect(True)
        self.configure(fg_color=get_color("colors.background.app", "#0A1428"))

        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        self._build_ui()
        self._setup_dragging()

        # Initial positioning snapped to League Client top edge
        self.after(50, self._sync_position_with_client)
        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Background thread to keep top drawer attached to League Client top edge
        threading.Thread(target=self._client_tracking_loop, daemon=True).start()

    def _build_ui(self):
        # Outer Gold Border Container
        self.outer_frame = ctk.CTkFrame(
            self,
            fg_color="#0A1428",
            border_width=2,
            border_color=get_color("colors.accent.gold", "#C8AA6E"),
            corner_radius=0
        )
        self.outer_frame.pack(fill="both", expand=True)

        # Top Header Bar
        self.header = ctk.CTkFrame(self.outer_frame, fg_color="#121C2A", height=32, corner_radius=0)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        ctk.CTkLabel(
            self.header,
            text="🎯 ARAM PRIORITY LIST — CLIENT TOP DRAWER",
            font=get_font("body", "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E")
        ).pack(side="left", padx=12)

        self.btn_close = ctk.CTkButton(
            self.header,
            text="✕",
            width=28,
            height=24,
            corner_radius=4,
            font=get_font("body", "bold"),
            fg_color="transparent",
            text_color="#FF4655",
            hover_color="#3A1924",
            command=self._on_close,
            cursor="hand2"
        )
        self.btn_close.pack(side="right", padx=6)

        # Grid Container
        self.body_frame = ctk.CTkFrame(self.outer_frame, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.grid_widget = PriorityIconGrid(self.body_frame, self.config, self.assets, expanded=True)
        self.grid_widget.pack(fill="both", expand=True)

    def _setup_dragging(self):
        self._drag_data = {"x": 0, "y": 0}
        self.header.bind("<ButtonPress-1>", self._on_drag_start)
        self.header.bind("<B1-Motion>", self._on_drag_motion)

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        x = self.winfo_x() - self._drag_data["x"] + event.x
        y = self.winfo_y() - self._drag_data["y"] + event.y
        self.geometry(f"+{x}+{y}")

    def _on_resize(self, event):
        """Dynamically adjust number of champion icons per row based on client / drawer width."""
        if event.widget != self:
            return
        w = event.width
        if w > 100:
            # Calculate icons per row based on container width (icon size 44px + 8px gap = 52px)
            icons_per_row = max(4, (w - 48) // 52)
            if hasattr(self, "grid_widget"):
                self.grid_widget.set_icons_per_row(icons_per_row)

    def _apply_geometry(self, drawer_w, drawer_h, target_x, target_y):
        try:
            if self.winfo_exists():
                self.geometry(f"{drawer_w}x{drawer_h}+{target_x}+{target_y}")
                if hasattr(self, "grid_widget"):
                    icons_per_row = max(4, (drawer_w - 48) // 52)
                    self.grid_widget.set_icons_per_row(icons_per_row)
        except Exception:
            pass

    def _sync_position_with_client(self):
        """Snap top-drawer geometry to match the width and top edge of the League Client window."""
        rect = _get_league_client_rect()
        if rect:
            cx, cy, cw, ch = rect
            drawer_w = max(500, cw)
            drawer_h = min(300, max(220, ch // 3))
            self._apply_geometry(drawer_w, drawer_h, cx, cy)
        else:
            self._apply_geometry(1000, 280, 100, 100)

    def _client_tracking_loop(self):
        """Background thread to keep drawer attached to top of League Client."""
        while getattr(self, "_tracking_active", False):
            try:
                rect = _get_league_client_rect()
                if rect:
                    cx, cy, cw, ch = rect
                    drawer_w = max(500, cw)
                    drawer_h = min(300, max(220, ch // 3))
                    target_geo = (drawer_w, drawer_h, cx, cy)
                else:
                    target_geo = (1000, 280, 100, 100)

                if target_geo != self._last_geo and self.winfo_exists():
                    self._last_geo = target_geo
                    w, h, x, y = target_geo
                    self.after(0, lambda w=w, h=h, x=x, y=y: self._apply_geometry(w, h, x, y))
            except Exception:
                pass
            time.sleep(0.5)

    def _on_close(self):
        self._tracking_active = False
        AramListWindow._instance = None
        self.destroy()

    @classmethod
    def open_window(cls, master, config, assets):
        """Open or focus existing AramListWindow instance."""
        if cls._instance is not None and cls._instance.winfo_exists():
            cls._instance.lift()
            cls._instance.focus_force()
        else:
            cls._instance = cls(master, config, assets)
        return cls._instance
