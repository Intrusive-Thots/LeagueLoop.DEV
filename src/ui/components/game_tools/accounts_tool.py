"""
Accounts Tool — Multi-Account Manager UI
─────────────────────────────────────────
Collapsible sidebar panel for managing multiple Riot accounts.
Provides add/edit/delete/reorder and one-click login switching.

Uses the same visual language as ArenaTool (collapsible header,
card-based list, icon badges).
"""
import customtkinter as ctk
import threading
from datetime import datetime

from ui.components.factory import get_color, get_font, get_radius
from ui.ui_shared import CTkTooltip
from core.constants import SPACING_SM, SPACING_MD


class AccountsTool(ctk.CTkFrame):
    """Multi-account manager with encrypted credential storage."""

    def __init__(self, master, account_manager, lcu=None, **kw):
        super().__init__(master, fg_color=get_color("colors.background.panel", "#0F1A24"), corner_radius=8, **kw)
        self.acct_mgr = account_manager
        self.lcu = lcu
        self.root_app = self.winfo_toplevel()

        self._expanded = False
        self._adding = False
        self._editing_idx = -1
        self._show_password = False
        self._detect_in_progress = False  # Item #116: Guard against concurrent detection threads

        self._build_header()
        self._build_body()
        self._render_accounts()

    # ─────────── Header ───────────
    def _build_header(self):
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=24)
        self.header.pack(fill="x", padx=SPACING_MD, pady=(SPACING_MD, 0))

        self.lbl_section = ctk.CTkLabel(
            self.header, text="▶  ACCOUNTS",
            font=get_font("caption", "bold"),
            text_color=get_color("colors.text.muted"), anchor="w",
            cursor="hand2"
        )
        self.lbl_section.pack(side="left", padx=2)
        CTkTooltip(self.lbl_section, "Toggle Account Manager")
        self.lbl_section.bind("<Button-1>", lambda e: self._toggle_collapse())
        self.lbl_section.bind("<Enter>", lambda e: self.lbl_section.configure(
            text_color=get_color("colors.text.primary")))
        self.lbl_section.bind("<Leave>", lambda e: self.lbl_section.configure(
            text_color=get_color("colors.text.muted")))

        # Account count badge
        self.lbl_count = ctk.CTkLabel(
            self.header, text="",
            font=("Inter", 9, "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"), anchor="w",
            width=20
        )
        self.lbl_count.pack(side="left", padx=(2, 0))

        # + Add button
        self.btn_add = ctk.CTkButton(
            self.header, text="+", width=20, height=20,
            corner_radius=10, font=get_font("body", "bold"),
            fg_color="transparent",
            text_color=get_color("colors.accent.primary"),
            hover_color=get_color("colors.state.hover"),
            command=self._show_add_form, cursor="hand2",
        )
        self.btn_add.pack(side="right")
        CTkTooltip(self.btn_add, "Add Account")

    def _update_header_count(self):
        count = self.acct_mgr.get_account_count()
        if count > 0:
            self.lbl_count.configure(text=f"({count})")
        else:
            self.lbl_count.configure(text="")

    # ─────────── Body ───────────
    def _build_body(self):
        self.body = ctk.CTkFrame(self, fg_color="transparent")

        # ── Add/Edit Form (hidden initially) ──
        self.form_container = ctk.CTkFrame(self.body, fg_color="transparent")

        self.form_title = ctk.CTkLabel(
            self.form_container, text="ADD ACCOUNT",
            font=get_font("caption", "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"), anchor="w"
        )
        self.form_title.pack(fill="x", padx=4, pady=(4, 4))

        # Label input
        lbl_row = ctk.CTkFrame(self.form_container, fg_color="transparent")
        lbl_row.pack(fill="x", padx=4, pady=(0, 2))
        ctk.CTkLabel(lbl_row, text="Label", font=get_font("caption"),
                     text_color=get_color("colors.text.muted"), width=60, anchor="w"
                     ).pack(side="left")
        self.entry_label = ctk.CTkEntry(
            lbl_row, placeholder_text="My Account",
            font=get_font("caption"), height=24,
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            border_color=get_color("colors.border.subtle"),
        )
        self.entry_label.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Riot login username input
        user_row = ctk.CTkFrame(self.form_container, fg_color="transparent")
        user_row.pack(fill="x", padx=4, pady=(0, 2))
        ctk.CTkLabel(user_row, text="Login", font=get_font("caption"),
                     text_color=get_color("colors.text.muted"), width=60, anchor="w"
                     ).pack(side="left")
        self.entry_username = ctk.CTkEntry(
            user_row, placeholder_text="riot login username",
            font=get_font("caption"), height=24,
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            border_color=get_color("colors.border.subtle"),
        )
        self.entry_username.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Password input
        pw_row = ctk.CTkFrame(self.form_container, fg_color="transparent")
        pw_row.pack(fill="x", padx=4, pady=(0, 2))
        ctk.CTkLabel(pw_row, text="Password", font=get_font("caption"),
                     text_color=get_color("colors.text.muted"), width=60, anchor="w"
                     ).pack(side="left")
        self.entry_password = ctk.CTkEntry(
            pw_row, placeholder_text="••••••••", show="•",
            font=get_font("caption"), height=24,
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            border_color=get_color("colors.border.subtle"),
        )
        self.entry_password.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Password visibility toggle
        self.btn_eye = ctk.CTkButton(
            pw_row, text="👁", width=24, height=24,
            corner_radius=get_radius("sm"), font=get_font("caption"),
            fg_color="transparent", hover_color=get_color("colors.state.hover"),
            text_color=get_color("colors.text.muted"),
            command=self._toggle_password_visibility, cursor="hand2",
        )
        self.btn_eye.pack(side="left", padx=(2, 0))
        CTkTooltip(self.btn_eye, "Toggle password visibility")

        # In-game Riot ID input (display name#tag)
        tag_row = ctk.CTkFrame(self.form_container, fg_color="transparent")
        tag_row.pack(fill="x", padx=4, pady=(0, 4))
        ctk.CTkLabel(tag_row, text="Riot ID", font=get_font("caption"),
                     text_color=get_color("colors.text.muted"), width=60, anchor="w"
                     ).pack(side="left")
        self.entry_tagline = ctk.CTkEntry(
            tag_row, placeholder_text="Name#TAG",
            font=get_font("caption"), height=24,
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            border_color=get_color("colors.border.subtle"),
        )
        self.entry_tagline.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Default Account checkbox
        default_row = ctk.CTkFrame(self.form_container, fg_color="transparent")
        default_row.pack(fill="x", padx=4, pady=(0, 4))
        ctk.CTkLabel(default_row, text="", width=60).pack(side="left")
        self.chk_default = ctk.CTkCheckBox(
            default_row, text="Set as Default Account",
            font=get_font("caption"),
            checkbox_width=14, checkbox_height=14,
            fg_color=get_color("colors.accent.primary"),
            hover_color=get_color("colors.state.hover"),
            text_color=get_color("colors.text.primary"),
            border_color=get_color("colors.border.subtle"),
        )
        self.chk_default.pack(side="left", padx=(4, 0))

        # Action buttons row
        btn_row = ctk.CTkFrame(self.form_container, fg_color="transparent")
        btn_row.pack(fill="x", padx=4, pady=(0, 4))

        self.btn_save = ctk.CTkButton(
            btn_row, text="💾 Save", height=24, width=60,
            corner_radius=get_radius("sm"), font=get_font("caption", "bold"),
            fg_color=get_color("colors.state.success"),
            hover_color="#00b359", text_color="#ffffff",
            command=self._save_form, cursor="hand2",
        )
        self.btn_save.pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_row, text="✕ Cancel", height=24, width=60,
            corner_radius=get_radius("sm"), font=get_font("caption", "bold"),
            fg_color="transparent", hover_color=get_color("colors.state.danger.muted", "#4d1111"),
            text_color=get_color("colors.state.danger", "#ff4444"), border_width=1, border_color=get_color("colors.state.danger", "#ff4444"),
            command=self._cancel_form, cursor="hand2",
        ).pack(side="left")

        # ── Account list ──
        self.list_frame = ctk.CTkScrollableFrame(
            self.body, fg_color="transparent", height=160,
            scrollbar_button_color=get_color("colors.text.disabled"),
            scrollbar_button_hover_color=get_color("colors.text.muted"),
            scrollbar_fg_color="transparent",
        )
        try:
            self.list_frame._scrollbar.configure(width=6)
        except Exception:
            pass
        self.list_frame.pack(fill="x")

    # ─────────── Collapse ───────────
    def _toggle_collapse(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.body.pack(fill="x", pady=(SPACING_SM, SPACING_MD), padx=SPACING_MD)
            self.lbl_section.configure(text="▼  ACCOUNTS")
            # Try to detect which account is active
            self._detect_active()
        else:
            self.body.pack_forget()
            self._cancel_form()
            self.lbl_section.configure(text="▶  ACCOUNTS")
        self._update_header_count()

    # ─────────── Form ───────────
    def _show_add_form(self):
        """Show the add-account form."""
        if not self._expanded:
            self._toggle_collapse()

        self._adding = True
        self._editing_idx = -1
        self.form_title.configure(text="ADD ACCOUNT", text_color=get_color("colors.accent.gold", "#C8AA6E"))
        self._clear_form()

        self.list_frame.pack_forget()
        self.form_container.pack(fill="x", padx=4, pady=(4, 0))
        self.list_frame.pack(fill="x")
        self.entry_label.focus_set()

    def _show_edit_form(self, idx):
        """Show the edit form pre-populated with account data."""
        accounts = self.acct_mgr.get_accounts()
        if not (0 <= idx < len(accounts)):
            return

        self._adding = False
        self._editing_idx = idx
        acct = accounts[idx]

        self.form_title.configure(text=f"EDIT — {acct.get('label', 'Account')}",
                                  text_color="#FFA726")
        self._clear_form()

        self.entry_label.insert(0, acct.get("label", ""))
        self.entry_username.insert(0, acct.get("username", ""))
        # Don't pre-fill password — user must re-enter if changing
        self.entry_tagline.insert(0, acct.get("tagline", ""))
        if acct.get("is_default", False):
            self.chk_default.select()
        else:
            self.chk_default.deselect()

        self.btn_save.configure(text="💾 Update")

        self.list_frame.pack_forget()
        self.form_container.pack(fill="x", padx=4, pady=(4, 0))
        self.list_frame.pack(fill="x")
        self.entry_label.focus_set()

    def _clear_form(self):
        self.entry_label.delete(0, "end")
        self.entry_username.delete(0, "end")
        self.entry_password.delete(0, "end")
        self.entry_tagline.delete(0, "end")
        self.entry_password.configure(show="•")
        self.chk_default.deselect()
        self._show_password = False
        self.btn_save.configure(text="💾 Save")

    def _cancel_form(self):
        self._adding = False
        self._editing_idx = -1
        self.form_container.pack_forget()

    def _toggle_password_visibility(self):
        self._show_password = not self._show_password
        self.entry_password.configure(show="" if self._show_password else "•")

    def _save_form(self):
        """Save or update an account from the form fields."""
        label = self.entry_label.get().strip()
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        tagline = self.entry_tagline.get().strip()
        is_default = (self.chk_default.get() == 1)

        if not label or not username:
            self._flash_field(self.entry_label if not label else self.entry_username)
            return

        if self._editing_idx >= 0:
            # Update existing
            self.acct_mgr.edit_account(
                self._editing_idx,
                label=label,
                username=username,
                password=password if password else None,  # Keep existing if blank
                tagline=tagline,
                is_default=is_default,
            )
            action = "updated"
        else:
            # Add new — password required
            if not password:
                self._flash_field(self.entry_password)
                return
            new_idx = self.acct_mgr.add_account(label, username, password, tagline)
            if is_default:
                self.acct_mgr.set_default_account(new_idx)
            action = "saved"

        self._cancel_form()
        self._render_accounts()

        try:
            from ui.components.toast import ToastManager
            ToastManager.get_instance().show(
                f"Account {action}: {label}",
                icon="🔐", theme="success"
            )
        except Exception:
            pass

    def _flash_field(self, entry):
        """Red flash on invalid field."""
        entry.configure(border_color="#e81123")
        self.after(800, lambda: entry.winfo_exists() and entry.configure(
            border_color=get_color("colors.border.subtle")))

    # ─────────── Active Detection ───────────
    def _detect_active(self):
        """Background detection of which account is currently logged in."""
        # Item #116: Prevent duplicate threads from rapid expand/collapse
        if self._detect_in_progress:
            return
        self._detect_in_progress = True

        def _detect():
            try:
                self.acct_mgr.detect_active_account()
                if self.winfo_exists():
                    self.root_app.after(0, self._render_accounts)
            finally:
                self._detect_in_progress = False
        threading.Thread(target=_detect, daemon=True).start()

    # ─────────── Render Account List ───────────
    def _render_accounts(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        accounts = self.acct_mgr.get_accounts()
        active_idx = self.acct_mgr.get_active_index()
        self._update_header_count()

        if not accounts:
            self._render_empty_state()
            return

        _card_bg = get_color("colors.background.card")
        _radius = get_radius("sm")

        for i, acct in enumerate(accounts):
            is_active = (i == active_idx)

            card = ctk.CTkFrame(
                self.list_frame,
                fg_color=_card_bg,
                corner_radius=_radius,
                border_width=1 if is_active else 0,
                border_color=get_color("colors.accent.gold", "#C8AA6E") if is_active else _card_bg,
            )
            card.pack(fill="x", pady=2, padx=2)

            # ── Top Row: Status + Label + Login Button ──
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=6, pady=(6, 0))

            # Active indicator — Item #118: Use Unicode dot with token colors instead of emojis
            dot_color = get_color("colors.state.success", "#00C853") if is_active else get_color("colors.text.disabled")
            ctk.CTkLabel(
                top, text="●", font=get_font("caption"),
                text_color=dot_color,
                width=14
            ).pack(side="left", padx=(0, 4))

            # Label
            label_text = acct.get("label", "Account")
            if acct.get("is_default", False):
                label_text = "★ " + label_text
            ctk.CTkLabel(
                top, text=label_text,
                font=get_font("caption", "bold"),
                text_color=get_color("colors.accent.gold", "#C8AA6E") if is_active or acct.get("is_default", False) else get_color("colors.text.primary"),
                anchor="w"
            ).pack(side="left", fill="x", expand=True)

            # Login / Sign-Out button
            # Check LCU connection — if disconnected, always show Login even for active account
            lcu_connected = self.lcu.is_connected if self.lcu else False
            has_credentials = bool(acct.get("password_enc"))

            if not is_active or not lcu_connected:
                btn_text = "▶ Login" if has_credentials else "⚠️ Update"
                btn_color = get_color("colors.accent.primary") if has_credentials else get_color("colors.state.warning", "#FFA726")
                btn_cmd = (lambda idx=i: self._login_account(idx)) if has_credentials else (lambda idx=i: self._show_edit_form(idx))
                btn_tooltip = f"Log in as {label_text}" if has_credentials else "Incomplete login details. Click to edit/update credentials."

                login_btn = ctk.CTkButton(
                    top, text=btn_text, width=56, height=20,
                    corner_radius=get_radius("sm"),
                    font=get_font("caption", "bold"),
                    fg_color=btn_color,
                    hover_color=get_color("colors.state.hover"),
                    text_color="#ffffff",
                    command=btn_cmd,
                    cursor="hand2",
                )
                login_btn.pack(side="right", padx=(4, 0))
                CTkTooltip(login_btn, btn_tooltip)

            if is_active:
                # Sign out button for active account
                signout_btn = ctk.CTkButton(
                    top, text="⏻ Sign Out", width=68, height=20,
                    corner_radius=get_radius("sm"),
                    font=get_font("caption", "bold"),
                    fg_color="transparent",
                    hover_color=get_color("colors.state.danger.muted", "#4d1111"),
                    text_color=get_color("colors.state.danger", "#ff4444"),
                    border_width=1, border_color=get_color("colors.state.danger", "#ff4444"),
                    command=self._sign_out_active,
                    cursor="hand2",
                )
                signout_btn.pack(side="right", padx=(4, 0))
                CTkTooltip(signout_btn, "Sign out of this account")

            # -- Bottom Row: Riot ID + Actions --
            bottom = ctk.CTkFrame(card, fg_color="transparent")
            bottom.pack(fill="x", padx=6, pady=(2, 6))

            riot_id = acct.get("tagline", "")
            if riot_id:
                display_sub = riot_id
            else:
                # Fallback: show login username if no Riot ID set
                display_sub = acct.get("username", "")
            ctk.CTkLabel(
                bottom,
                text=display_sub,
                font=("Inter", 10),
                text_color=get_color("colors.text.muted"),
                anchor="w"
            ).pack(side="left", fill="x", expand=True)

            # Last used
            last_used = acct.get("last_used")
            if last_used:
                relative = self._relative_time(last_used)
                ctk.CTkLabel(
                    bottom, text=relative,
                    font=("Inter", 9),
                    text_color=get_color("colors.text.disabled"),
                ).pack(side="left", padx=(4, 0))

            # Action buttons
            action_frame = ctk.CTkFrame(bottom, fg_color="transparent")
            action_frame.pack(side="right")

            # Move up
            if i > 0:
                ctk.CTkButton(
                    action_frame, text="▲", width=18, height=18,
                    corner_radius=get_radius("sm"), font=get_font("caption"),
                    fg_color="transparent", hover_color=get_color("colors.state.hover"),
                    text_color=get_color("colors.text.muted"),
                    command=lambda idx=i: self._move_account(idx, -1),
                    cursor="hand2"
                ).pack(side="left", padx=0)

            # Move down
            if i < len(accounts) - 1:
                ctk.CTkButton(
                    action_frame, text="▼", width=18, height=18,
                    corner_radius=get_radius("sm"), font=get_font("caption"),
                    fg_color="transparent", hover_color=get_color("colors.state.hover"),
                    text_color=get_color("colors.text.muted"),
                    command=lambda idx=i: self._move_account(idx, 1),
                    cursor="hand2"
                ).pack(side="left", padx=0)

            # Edit
            ctk.CTkButton(
                action_frame, text="✎", width=20, height=20,
                corner_radius=get_radius("sm"), font=get_font("caption"),
                fg_color="transparent", hover_color=get_color("colors.state.hover"),
                text_color=get_color("colors.accent.gold", "#C8AA6E"),
                command=lambda idx=i: self._show_edit_form(idx),
                cursor="hand2"
            ).pack(side="left", padx=(0, 2))

            # Delete
            ctk.CTkButton(
                action_frame, text="✕", width=20, height=20,
                corner_radius=get_radius("sm"), font=get_font("caption", "bold"),
                fg_color="transparent", hover_color=get_color("colors.state.danger.muted", "#4d1111"),
                text_color=get_color("colors.state.danger", "#ff4444"),
                command=lambda idx=i: self._delete_account(idx),
                cursor="hand2"
            ).pack(side="left")

    def _render_empty_state(self):
        """Rich empty state with explanation."""
        empty_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        empty_frame.pack(fill="x", pady=8, padx=6)

        ctk.CTkLabel(
            empty_frame,
            text="Multi-Account Manager",
            font=get_font("caption", "bold"),
            text_color=get_color("colors.text.primary"),
            anchor="w"
        ).pack(fill="x", pady=(0, 4))

        for line in [
            "① Save login credentials for multiple accounts",
            "② Switch accounts with one click",
            "③ Passwords are encrypted (Windows DPAPI)",
            "④ Auto-detects which account is active",
        ]:
            ctk.CTkLabel(
                empty_frame, text=line,
                font=("Inter", 10), text_color=get_color("colors.text.muted"),
                anchor="w"
            ).pack(fill="x", padx=(8, 0))

        ctk.CTkButton(
            empty_frame,
            text="+ Add First Account",
            font=get_font("body", "bold"),
            fg_color=get_color("colors.accent.primary"),
            text_color="#ffffff",
            hover_color=get_color("colors.state.hover"),
            height=36,
            corner_radius=8,
            command=self._show_add_form,
            cursor="hand2"
        ).pack(fill="x", pady=(8, 0))

    # ─────────── Actions ───────────
    def _get_sidebar(self):
        """Walk up the widget tree to find the SidebarWidget."""
        widget = self.master
        while widget is not None:
            if hasattr(widget, "update_action_log"):
                return widget
            widget = getattr(widget, "master", None)
        return None

    def _log_message(self, msg):
        """Send a log message to both toast and sidebar action log."""
        try:
            from ui.components.toast import ToastManager
            ToastManager.get_instance().show(msg, icon="🔐", duration=3000)
        except Exception:
            pass

        sidebar = self._get_sidebar()
        if sidebar:
            try:
                sidebar.update_action_log(msg)
            except Exception:
                pass

    def _login_account(self, idx):
        """Trigger login for the specified account."""
        def _completion(success):
            if self.winfo_exists():
                self.after(3000, self._detect_active)

        self.acct_mgr.login_account(idx, log_func=self._log_message, completion_func=_completion)

    def _sign_out_active(self):
        """Sign out the currently active account."""
        def _completion(success):
            if self.winfo_exists():
                self.after(1000, self._render_accounts)
                self.after(1500, self._detect_active)

        self.acct_mgr.sign_out(log_func=self._log_message, completion_func=_completion)

    def _delete_account(self, idx):
        accounts = self.acct_mgr.get_accounts()
        if 0 <= idx < len(accounts):
            label = accounts[idx].get("label", "Account")
            self.acct_mgr.delete_account(idx)
            self._render_accounts()

            try:
                from ui.components.toast import ToastManager
                ToastManager.get_instance().show(
                    f"Removed: {label}", icon="🗑️", theme="warning"
                )
            except Exception:
                pass

    def _move_account(self, idx, direction):
        self.acct_mgr.move_account(idx, direction)
        self._render_accounts()

    @staticmethod
    def _relative_time(iso_str):
        """Convert ISO timestamp to relative time string."""
        try:
            dt = datetime.fromisoformat(iso_str)
            # Item #125: Handle timezone-aware ISO strings by comparing in same tz
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            diff = now - dt
            seconds = int(diff.total_seconds())

            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                mins = seconds // 60
                return f"{mins}m ago"
            elif seconds < 86400:
                hours = seconds // 3600
                return f"{hours}h ago"
            else:
                days = seconds // 86400
                return f"{days}d ago"
        except Exception:
            return ""
