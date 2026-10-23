"""
Friend Priority List — Rebuilt V2
──────────────────────────────────
Grid-based friend rows with proper scroll/input separation,
deterministic layout, and tokenized styling throughout.

Structure:
  ┌─────────────────────────┐
  │ ▼ FRIEND LIST   [actions]│  ← header (grid)
  ├─────────────────────────┤
  │ [SCROLLABLE FRIEND LIST]│  ← scroll area (pack, isolated)
  │  ┌ icon ┬ name  ┬ ⚭ ┐  │
  │  │      │ status│   │  │
  │  └──────┴───────┴───┘  │
  └─────────────────────────┘
"""
import threading
from core.events import EventBus
import tkinter as tk
import customtkinter as ctk
from ui.components.glyphs import set_icon
from services import friend_presence

from ui.components.factory import get_color, get_font, get_radius
from ui.ui_shared import CTkTooltip
from core.constants import ROW_HEIGHT, ICON_SIZE, PADDING_X
from utils.logger import Logger
from utils.smooth_scroll import apply_smooth_scroll


#: Longest name / status that fits beside the icon in the ~280 px sidebar.
NAME_MAX_CHARS = 18
STATUS_MAX_CHARS = 26


def _ellipsize(text, limit):
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _presence_color(kind):
    """Dot colour for a presence kind from ``friend_presence.describe``."""
    return friend_presence.COLORS.get((kind or "").lower(), friend_presence.COLORS["offline"])


class FriendRow(ctk.CTkFrame):
    """A single friend entry using grid layout for deterministic column alignment."""

    def __init__(self, master, name, status_text, availability, icon_widget_cb=None,
                 is_auto_join=False, on_toggle_auto_join=None, on_context_menu=None, **kw):
        """Initializes the FriendRow."""
        super().__init__(master, height=ROW_HEIGHT + 4, fg_color="transparent", cursor="hand2", **kw)
        self.grid_columnconfigure(2, weight=1)  # Name column expands
        self.grid_propagate(False)

        self._name = name
        self._on_toggle = on_toggle_auto_join
        self._on_context = on_context_menu

        # Hover feedback
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        # Col 0: Profile Icon
        self.icon_frame = ctk.CTkFrame(self, fg_color="transparent", width=ICON_SIZE, height=ICON_SIZE)
        self.icon_frame.grid(row=0, column=0, rowspan=2, padx=(PADDING_X, 6), pady=4, sticky="w")
        self.icon_frame.grid_propagate(False)
        self.icon_lbl = ctk.CTkLabel(self.icon_frame, text="")
        self.icon_lbl.pack(expand=True, fill="both")

        # Async icon loading callback
        if icon_widget_cb:
            icon_widget_cb(self.icon_lbl)

        # Col 1: Status Dot — League's own presence colours: green = online,
        # amber = away / in game, grey = offline. Offline was red before, which
        # read as an error on every friend who simply was not playing.
        is_online = availability not in ("offline", "", None)
        is_league = availability in ("chat", "away", "ingame")
        dot_color = _presence_color(availability)
        self.status_dot = ctk.CTkLabel(
            self, text="●", text_color=dot_color,
            font=get_font("body"), width=14
        )
        self.status_dot.grid(row=0, column=1, rowspan=2, padx=(0, 4), sticky="w")
        CTkTooltip(self.status_dot, status_text or availability)

        # Col 2: Name + Status Text (stacked)
        name_color = get_color("colors.accent.primary") if is_league else "#8A93A0"
        self.lbl_name = ctk.CTkLabel(
            self, text=_ellipsize(name, NAME_MAX_CHARS),
            font=get_font("body", "bold"),
            text_color=name_color,
            anchor="w", height=18,
        )
        self.lbl_name.grid(row=0, column=2, sticky="sew", pady=(4, 0))

        status_color = "#A0A7B4" if is_online else "#8A93A0"
        self.lbl_status = ctk.CTkLabel(
            self, text=_ellipsize(status_text, STATUS_MAX_CHARS),
            font=get_font("caption"),
            text_color=status_color,
            anchor="w", height=14,
        )
        # CTkLabel defaults to 28px tall; two of those in a 40px row clipped
        # the status line away entirely (seen on the live client).
        self.lbl_status.grid(row=1, column=2, sticky="new", pady=(0, 4))
        if len(name) > NAME_MAX_CHARS or len(status_text or "") > STATUS_MAX_CHARS:
            CTkTooltip(self.lbl_name, f"{name} — {status_text}" if status_text else name)

        # Col 3: Auto-Join Indicator
        aj_color = get_color("colors.accent.gold", "#C8AA6E") if is_auto_join else "#4A5562"
        aj_tip = "Auto-Join Active — Click to toggle" if is_auto_join else "Auto-Join Inactive — Click to toggle"
        self.auto_join_lbl = ctk.CTkLabel(
            self, text="⚭", font=get_font("title", "bold"),
            text_color=aj_color, cursor="hand2", width=24
        )
        self.auto_join_lbl.grid(row=0, column=3, rowspan=2, padx=(4, PADDING_X), sticky="e")
        CTkTooltip(self.auto_join_lbl, aj_tip)

        # Left-click toggle on auto-join icon (Item #154)
        self.auto_join_lbl.bind("<Button-1>", lambda e: self._on_toggle(self._name) if self._on_toggle else None)

        # Right-click context menu on all widgets
        for w in [self, self.icon_lbl, self.status_dot, self.lbl_name, self.lbl_status, self.auto_join_lbl]:
            w.bind("<Button-3>", self._popup_context)
            # Propagate hover to parent row
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        self.configure(fg_color=get_color("colors.state.hover"))

    def _on_leave(self, e):
        self.configure(fg_color="transparent")

    def _popup_context(self, e):
        if self._on_context:
            self._on_context(e, self._name)


class FriendPriorityList(ctk.CTkFrame):
    """Rebuilt friend list with grid-based rows and separated scroll/input areas."""

    def __init__(self, master, config, lcu=None, **kw):
        """Initializes the FriendPriorityList widget."""
        super().__init__(master, fg_color="transparent", **kw)

        self.config = config
        self.lcu = lcu

        self._is_expanded_state = True
        self._friends_data = []
        self._auto_join_names = {
            f.get("name", "").lower(): f.get("enabled", True)
            for f in self.config.get("auto_join_list", [])
        }
        self._last_render_sig = None
        self._row_widgets = []  # Track FriendRow instances for cleanup

        self._build_ui()

        # Subscribe to EventBus — WebSocket pushes friends data in real-time
        EventBus.on("friends_event", self._on_friends_event)

        # One-shot initial fetch in case WS hasn't pushed data yet
        if self.lcu:
            self.after(500, self._initial_fetch)

        # Periodic refresh to catch missed WebSocket events
        self._refresh_interval_ms = 30000  # 30 seconds
        self._start_periodic_refresh()

    # ─────────── Config Persistence ───────────

    def _save_priority_list(self):
        lst = [{"name": name, "enabled": enabled} for name, enabled in self._auto_join_names.items()]
        self.config.set("auto_join_list", lst)

    # ─────────── Collapse / Expand Controls ───────────

    @property
    def _expanded(self) -> bool:
        ctrl = getattr(getattr(self, "card", None), "_toggle_controller", None)
        if ctrl is not None:
            return getattr(ctrl, "is_expanded", True)
        return getattr(self, "_is_expanded_state", True)

    @_expanded.setter
    def _expanded(self, val: bool) -> None:
        self._is_expanded_state = bool(val)

    def _toggle_collapse(self) -> None:
        """Toggle collapsed state of the friend list card."""
        ctrl = getattr(getattr(self, "card", None), "_toggle_controller", None)
        if ctrl is not None:
            ctrl.toggle()
            self._is_expanded_state = getattr(ctrl, "is_expanded", True)
        else:
            self._is_expanded_state = not getattr(self, "_is_expanded_state", True)

    def collapse(self) -> None:
        """Collapse the friend list card if currently expanded."""
        if self._expanded:
            self._toggle_collapse()

    def expand(self) -> None:
        """Expand the friend list card if currently collapsed."""
        if not self._expanded:
            self._toggle_collapse()

    # ─────────── UI Construction ───────────

    def _build_ui(self):
        from ui.components.factory import make_card
        self.card = make_card(
            self, title="FRIEND LIST",
            collapsible=True, start_collapsed=False,
            padx=0, pady=0
        )
        self.header = self.card._header
        self.body = self.card

        # Online count badge
        self.lbl_online_count = ctk.CTkLabel(
            self.header, text="0", width=22, height=18,
            corner_radius=9, fg_color=get_color("colors.text.muted"),
            text_color=get_color("colors.background.app"),
            font=get_font("caption", "bold")
        )
        self.lbl_online_count.pack(side="left", padx=(4, 0))

        # Export button
        self.btn_export = ctk.CTkButton(
            self.header, text="⎘", width=20, height=20,
            corner_radius=4, font=get_font("body"),
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover"),
            command=self._export_list, cursor="hand2",
        )
        self.btn_export.pack(side="right", padx=(0, 2))
        CTkTooltip(self.btn_export, "Export List to Clipboard")

        # Mass Invite button
        self.btn_mass_invite = ctk.CTkButton(
            self.header, text=" Invite All", width=84, height=20,
            corner_radius=get_radius("sm"), font=get_font("caption", "bold"),
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover"),
            command=self._on_mass_invite,
            cursor="hand2",
        )
        set_icon(self.btn_mass_invite, "person", "#A0A7B4", 12)
        self.btn_mass_invite.pack(side="right")
        CTkTooltip(self.btn_mass_invite, "Invite all online friends (or VIPs) to your lobby")

        # Scroll Area
        self.scroll = ctk.CTkScrollableFrame(
            self.body, fg_color="transparent", height=140,
            scrollbar_button_color=get_color("colors.text.disabled"),
            scrollbar_button_hover_color=get_color("colors.text.muted"),
            scrollbar_fg_color="transparent",
        )
        try:
            self.scroll._scrollbar.configure(width=6)
        except Exception as exc:
            Logger.debug("FriendList", "_build_ui suppressed an error", exc=exc)
        self.scroll.pack(fill="both", expand=True)
        apply_smooth_scroll(self.scroll)

        # The list_parent lives inside the scroll frame
        self.list_parent = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.list_parent.pack(fill="x")

        # First frame: say why the list is empty instead of a blank box.
        self._render_empty_state()
        self._sync_header_actions(0, 0)

    def _client_connected(self) -> bool:
        lcu = getattr(self, "lcu", None)
        return bool(lcu is not None and getattr(lcu, "is_connected", False) is True)

    def _render_empty_state(self):
        """Explain an empty list: client offline vs. still loading."""
        if self._client_connected():
            title, hint = "Loading friends…", "Pulling your friend list from the client."
        else:
            title, hint = "No client connected", "Friends show up here once League is running."
        ctk.CTkLabel(
            self.list_parent, text=title,
            font=get_font("body", "bold"),
            text_color="#A0A7B4",
        ).pack(pady=(28, 2))
        ctk.CTkLabel(
            self.list_parent, text=hint,
            font=get_font("caption"),
            text_color="#8A93A0",
            wraplength=220, justify="center",
        ).pack(pady=(0, 20))

    def _sync_header_actions(self, online_count: int, total_count: int = 0):
        """Invite All needs someone online; Export needs a list. Disable otherwise."""
        pairs = (
            (getattr(self, "btn_mass_invite", None), online_count > 0),
            (getattr(self, "btn_export", None), total_count > 0),
        )
        for btn, enabled in pairs:
            state = "normal" if enabled else "disabled"
            if btn is None:
                continue
            try:
                btn.configure(state=state)
            except Exception as exc:
                Logger.debug("FriendList", "_sync_header_actions suppressed an error", exc=exc)

    # ─────────── Data Fetching (EventBus-driven) ───────────

    def _on_friends_event(self, friends_data):
        """Called by EventBus when LCU WebSocket pushes friend updates."""
        if not friends_data:
            return
        if isinstance(friends_data, list):
            self._process_friends(friends_data)
        elif isinstance(friends_data, dict):
            # WAMP delta update — merge into cached data instead of discarding
            self._merge_friend_delta(friends_data)

    def _initial_fetch(self, force=False):
        """Fetch full friends list. Called on init and periodically for reliability."""
        if not force and self._friends_data:  # Already got data from WS on initial load
            return
        try:
            if not self.winfo_exists() or not self.lcu:
                return
        except Exception:
            return

        def task():
            """Background task."""
            try:
                res = self.lcu.request("GET", "/lol-chat/v1/friends", silent=True)
                if res and res.status_code == 200:
                    self._process_friends(res.json())
            except Exception as e:
                Logger.debug("FriendList", f"Initial fetch error: {e}")

        threading.Thread(target=task, daemon=True).start()

    def _merge_friend_delta(self, delta):
        """Merge a single friend delta update into cached data."""
        if not isinstance(delta, dict):
            return
        puuid = delta.get("puuid") or delta.get("id")
        if not puuid:
            # Can't identify friend — fall back to full refresh
            self._initial_fetch(force=True)
            return
        
        # Find and update existing entry, or append
        updated = False
        for i, f in enumerate(self._friends_data):
            if f.get("puuid") == puuid or f.get("id") == puuid:
                self._friends_data[i].update(delta)
                updated = True
                break
        
        if not updated:
            self._friends_data.append(delta)
        
        # Re-sort and re-render
        self._process_friends(self._friends_data)

    def _start_periodic_refresh(self):
        """Periodically re-fetch the full friends list to stay accurate."""
        def _tick():
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return
            self._initial_fetch(force=True)
            self._refresh_timer = self.after(self._refresh_interval_ms, _tick)
        
        self._refresh_timer = self.after(self._refresh_interval_ms, _tick)

    def _process_friends(self, friends):
        """Sort + render friends data (callable from any thread)."""
        for f in friends:
            f["_name_lower"] = (f.get("gameName", "") or f.get("name", "")).lower()

        def sort_key(f):
            """Sorting key function."""
            gn = f.get("_name_lower", (f.get("gameName", "") or f.get("name", "")).lower())
            # Invitable first, then mobile / other Riot games, then offline.
            if friend_presence.is_invitable(f):
                prio = 0
            elif friend_presence.is_online(f):
                prio = 1 if friend_presence.describe(f)[0] != "other" else 2
            else:
                prio = 3
            return (prio, gn)

        friends.sort(key=sort_key)
        self._friends_data = friends

        # Marshal render to main thread
        try:
            EventBus.invoke_thread_safe(self, self._safe_render)
        except Exception as exc:
            Logger.debug("FriendList", "_process_friends suppressed an error", exc=exc)

    def _safe_render(self):
        """Thread-safe render wrapper."""
        try:
            if self.winfo_exists():
                self._render_list()
        except Exception as exc:
            Logger.debug("FriendList", "_safe_render suppressed an error", exc=exc)

    # ─────────── Auto-Join Toggle ───────────

    def _toggle_auto_join(self, name):
        name_lower = name.lower()
        self._auto_join_names[name_lower] = not self._auto_join_names.get(name_lower, False)
        self._save_priority_list()
        self._last_render_sig = None  # Force re-render
        self._render_list()
        if hasattr(self, "automation") and self.automation:
            self.automation.reset_auto_join_cooldowns(name)

    # ─────────── Context Menu ───────────

    def _show_context_menu(self, event, friend_name):
        menu = tk.Menu(
            self, tearoff=0,
            bg=get_color("colors.background.card"),
            fg=get_color("colors.text.primary", "#F0E6D2"),
            activebackground=get_color("colors.state.hover"),
            activeforeground=get_color("colors.text.primary"),
            relief="solid",  # lift the popup off the panel it opens over
            borderwidth=1,
            activeborderwidth=0,
            font=("Inter", -12),  # negative = pixels, matching CTk body size
        )
        try:
            menu.configure(bg="#1E2832", activebackground="#2A3644")
        except Exception as exc:
            Logger.debug("FriendList", "menu colour unavailable", exc=exc)

        name_lower = friend_name.lower()
        is_auto = self._auto_join_names.get(name_lower, False)
        label = "Disable Auto-Join" if is_auto else "Enable Auto-Join"
        try:  # drawn glyph instead of a ✕/✓ text symbol (#31)
            from PIL import ImageTk
            from ui.components.glyphs import glyph_image
            glyph = glyph_image("close" if is_auto else "check",
                                "#FF7A70" if is_auto else "#2ECC71", 12)
            menu._ll_img = ImageTk.PhotoImage(glyph, master=menu)  # keep a reference
            menu.add_command(label="  " + label, image=menu._ll_img, compound="left",
                             command=lambda: self._toggle_auto_join(friend_name))
        except Exception as exc:
            Logger.debug("FriendList", "menu glyph unavailable", exc=exc)
            menu.add_command(label=label, command=lambda: self._toggle_auto_join(friend_name))

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ─────────── Render Signature (Dedup) ───────────

    def _get_render_signature(self):
        sig = []
        for f in self._friends_data:
            name = f.get("gameName", "") or f.get("name", "")
            avail = f.get("availability", "offline")
            msg = friend_presence.describe(f)[1]
            name_lower = f.get("_name_lower", name.lower())
            is_auto = self._auto_join_names.get(name_lower, False)
            sig.append(f"{name}|{avail}|{msg}|{is_auto}")
        return "|".join(sig)

    # ─────────── Rendering ───────────

    def _render_list(self):
        if not self.winfo_exists():
            return

        sig = self._get_render_signature()
        if self._last_render_sig == sig:
            return
        self._last_render_sig = sig

        # Destroy old rows
        for w in self._row_widgets:
            try:
                w.destroy()
            except Exception as exc:
                Logger.debug("FriendList", "_render_list suppressed an error", exc=exc)
        self._row_widgets.clear()

        for w in self.list_parent.winfo_children():
            w.destroy()

        # Update online count badge
        # Count who can actually take a lobby invite: the live payload had
        # mobile and VALORANT friends counted as "online" before.
        online_count = sum(1 for f in self._friends_data if friend_presence.is_invitable(f))
        total_count = len(self._friends_data)
        if hasattr(self, "lbl_online_count"):
            self.lbl_online_count.configure(text=str(online_count))
            if online_count > 0:
                self.lbl_online_count.configure(fg_color=get_color("colors.state.success"))
            else:
                self.lbl_online_count.configure(fg_color=get_color("colors.text.muted"))

        self._sync_header_actions(online_count, total_count)
        if not self._friends_data:
            self._render_empty_state()
            return

        # Hoist assets lookup outside the loop
        root = self.winfo_toplevel()
        assets = getattr(root, "assets", None)

        for item in self._friends_data:
            name = item.get("gameName", "") or item.get("name", "")
            if not name:
                continue

            avail, status_msg = friend_presence.describe(item)

            name_lower = item.get("_name_lower", name.lower())
            is_auto = self._auto_join_names.get(name_lower, False)

            # Build icon loading callback
            def make_icon_cb(asset_mgr, icon_id):
                """Creates an icon callback."""
                def cb(label_widget):
                    """Callback function."""
                    if asset_mgr and hasattr(asset_mgr, "get_icon_async"):
                        asset_mgr.get_icon_async(
                            "profileicon", str(icon_id),
                            lambda img, l=label_widget: l.configure(image=img) if l.winfo_exists() else None,
                            size=(ICON_SIZE, ICON_SIZE), widget=label_widget
                        )
                return cb

            icon_id = item.get("icon", 1)
            if not isinstance(icon_id, int) or icon_id < 0:
                icon_id = 1  # DDragon returns 403 for invalid icon IDs like -1
            icon_cb = make_icon_cb(assets, icon_id)

            row = FriendRow(
                self.list_parent,
                name=name,
                status_text=status_msg,
                availability=avail,
                icon_widget_cb=icon_cb,
                is_auto_join=is_auto,
                on_toggle_auto_join=self._toggle_auto_join,
                on_context_menu=self._show_context_menu,
            )
            row.pack(fill="x", pady=1)
            self._row_widgets.append(row)

    # ─────────── Export ───────────

    def _export_list(self):
        """Copies the active Friend Auto-Join list to the clipboard."""
        from ui.components.toast import ToastManager
        if not self._friends_data:
            ToastManager.get_instance().show("Friend list is empty!", icon="warning", theme="error")
            return

        names = [f.get("name", "") for f in self._friends_data if f.get("name", "")]
        export_str = "\n".join(names)

        self.clipboard_clear()
        self.clipboard_append(export_str)
        self.update()

        ToastManager.get_instance().show(
            "Friend List Copied!",
            icon="check",
            theme="success",
            confetti=True
        )

    # ─────────── Mass Invite ───────────

    def _on_mass_invite(self):
        """Delegate mass invite to the automation engine via the widget tree."""
        root = self.winfo_toplevel()
        engine = getattr(root, "automation", None)
        if engine:
            threading.Thread(target=engine.mass_invite_friends, daemon=True).start()
        else:
            try:
                from ui.components.toast import ToastManager
                ToastManager.get_instance().show("Automation engine not available.", icon="warning", theme="error")
            except Exception as exc:
                Logger.debug("FriendList", "_on_mass_invite suppressed an error", exc=exc)

    def destroy(self):
        try:
            from core.events import EventBus
            EventBus.off("friends_event", self._on_friends_event)
        except Exception as exc:
            Logger.debug("FriendList", "destroy suppressed an error", exc=exc)
        if getattr(self, "_refresh_timer", None) is not None:
            try:
                self.after_cancel(self._refresh_timer)
                self._refresh_timer = None
            except Exception as exc:
                Logger.debug("FriendList", "destroy suppressed an error", exc=exc)
        super().destroy()

