"""
Diagnostics — is LeagueLoop working, and if not, what is wrong (§58).

This screen used to be four telemetry counters (average HTTP latency, P95
latency, websocket event total, disk cache MB) above an empty SQLite table.
All of it read zero on a fresh launch, none of it told you whether the app
was doing its job, and the only action offered was "Prune Cache" — a
maintenance chore as the page's primary button.

What someone opening a page called Diagnostics actually wants to know: is the
client connected, is automation running, did champion data load, what failed
last, and how do I hand that to someone who can help.

The engineering counters are still here, under a disclosure, because they are
occasionally useful — but they are not the page.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSeparator
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import TEXT_MUTED, TEXT_SECONDARY
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import TEXT_CAPTION, TEXT_MICRO, TEXT_PAGE_TITLE


class QtDiagnosticsTab(QWidget):
    """Health first, telemetry second."""

    def __init__(self, container=None, view_model=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.container = container
        self.view_model = view_model
        self.lcu = getattr(container, "lcu", None) if container else None
        self.assets = getattr(container, "assets", None) if container else None
        self.db = getattr(container, "db", None) if container else None

        self._checks: List[Tuple[str, LLStatus]] = []
        self._details_open = False

        self._setup_ui()
        self.refresh()

        if view_model is not None:
            view_model.state_changed.connect(self.refresh)

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        header = QHBoxLayout()
        header.setSpacing(SPACE_SM)
        title = QLabel("Diagnostics", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        header.addWidget(title)
        header.addStretch(1)

        self.btn_copy = LLButton(
            "Copy report", variant=ButtonVariant.PRIMARY, size=ButtonSize.SM, parent=self
        )
        self.btn_copy.setToolTip(
            "Copy everything on this page as text, for a bug report"
        )
        self.btn_copy.clicked.connect(self._on_copy)
        header.addWidget(self.btn_copy)

        self.btn_refresh = LLButton(
            "Refresh", variant=ButtonVariant.SECONDARY, size=ButtonSize.SM, parent=self
        )
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)
        root.addLayout(header)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        body = QVBoxLayout(holder)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(SPACE_MD)

        # --- health -------------------------------------------------------
        self.health_card = LLCard(title="Health", parent=holder)
        for key, label in (
            ("client", "League Client"),
            ("accounts", "Account switching"),
            ("automation", "Automation"),
            ("champions", "Champion data"),
            ("history", "Match history"),
        ):
            if self._checks:
                self.health_card.add_widget(LLSeparator(parent=self.health_card))
            row = QWidget(self.health_card)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 2, 0, 2)
            row_layout.setSpacing(SPACE_MD)

            name = QLabel(label, row)
            name.setStyleSheet(
                TEXT_MICRO.qss(color=TEXT_SECONDARY) + " background: transparent;"
            )
            name.setFixedWidth(150)
            row_layout.addWidget(name)

            status = LLStatus("Checking…", Tone.NEUTRAL, "", parent=row)
            row_layout.addWidget(status, 1)

            self.health_card.add_widget(row)
            self._checks.append((key, status))
        body.addWidget(self.health_card)

        # --- developer details (collapsed) --------------------------------
        details_header = QHBoxLayout()
        self.btn_details = LLButton(
            "Show developer details",
            variant=ButtonVariant.GHOST,
            size=ButtonSize.SM,
            parent=holder,
        )
        self.btn_details.clicked.connect(self._toggle_details)
        details_header.addWidget(self.btn_details)
        details_header.addStretch(1)
        body.addLayout(details_header)

        # Developer Mode was a Settings switch writing `developer_mode`, a key
        # nothing read. §58 wants the engineering view behind it; without a
        # consumer the switch did nothing and the telemetry was always one
        # click away regardless.
        self.btn_details.setVisible(self._developer_mode())

        self.details_card = LLCard(title="Developer details", parent=holder)
        self.metrics_label = QLabel("", self.details_card)
        self.metrics_label.setWordWrap(True)
        self.metrics_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.metrics_label.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.details_card.add_widget(self.metrics_label)

        prune_row = QHBoxLayout()
        prune_row.addStretch(1)
        self.btn_prune = LLButton(
            "Prune image cache",
            variant=ButtonVariant.SECONDARY,
            size=ButtonSize.SM,
            parent=self.details_card,
        )
        self.btn_prune.setToolTip("Delete old cached champion art to free disk space")
        self.btn_prune.clicked.connect(self._on_prune)
        prune_row.addWidget(self.btn_prune)
        self.details_card.add_layout(prune_row)

        self.details_card.setVisible(False)
        body.addWidget(self.details_card)

        body.addStretch(1)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

    # -------------------------------------------------------------- checks
    def _developer_mode(self) -> bool:
        config = getattr(self.container, "config", None) if self.container else None
        if config is None:
            return False
        try:
            return bool(config.get("developer_mode", False))
        except Exception:
            return False

    def set_developer_mode(self, enabled: bool) -> None:
        """Show or hide the engineering view, and collapse it when hidden."""
        self.btn_details.setVisible(bool(enabled))
        if not enabled and self._details_open:
            self._toggle_details()

    def _status(self, key: str):
        for name, widget in self._checks:
            if name == key:
                return widget
        return None

    def refresh(self, *_args) -> None:
        """Re-run every check. Cheap: all of it is already-held state."""
        self._set("client", *self._check_client())
        self._set("accounts", *self._check_accounts())
        self._set("automation", *self._check_automation())
        self._set("champions", *self._check_champions())
        self._set("history", *self._check_history())
        if self._details_open:
            self._render_metrics()

    def _set(self, key: str, text: str, tone: Tone, detail: str) -> None:
        widget = self._status(key)
        if widget is not None:
            widget.set_status(text, tone, detail)

    def _check_client(self) -> Tuple[str, Tone, str]:
        state = self.view_model.state.client if self.view_model else None
        if state is not None and state.connected:
            who = state.summoner_name or "signed in"
            return ("Connected", Tone.SUCCESS, "{} · {}".format(who, state.phase))
        if self.lcu is not None and getattr(self.lcu, "is_connected", False):
            return ("Connected", Tone.SUCCESS, "")
        return (
            "Not connected", Tone.WARNING,
            "Start the League Client. Most of LeagueLoop needs it.",
        )

    def _check_accounts(self) -> Tuple[str, Tone, str]:
        manager = getattr(self.container, "account_manager", None) if self.container else None
        if manager is None:
            return ("Unavailable", Tone.DANGER, "The account manager did not start.")
        if getattr(manager, "_switcher", None) is None:
            return ("Unavailable", Tone.DANGER, "The account switcher did not build.")
        try:
            count = len(manager.get_accounts() or [])
        except Exception as exc:
            return ("Error", Tone.DANGER, str(exc))
        if not count:
            return ("No accounts stored", Tone.NEUTRAL, "Add one on the Accounts screen.")
        return (
            "Ready", Tone.SUCCESS,
            "{} account{} stored".format(count, "" if count == 1 else "s"),
        )

    def _check_automation(self) -> Tuple[str, Tone, str]:
        auto = self.view_model.state.automation if self.view_model else None
        if auto is None:
            return ("Unknown", Tone.NEUTRAL, "")
        if auto.last_error:
            return ("Last run failed", Tone.DANGER, auto.last_error)
        if not auto.running:
            return ("Off", Tone.NEUTRAL, "Nothing will run automatically.")
        if auto.paused:
            return ("Paused", Tone.WARNING, "On, but held until you resume.")
        return ("Running", Tone.SUCCESS, "")

    def _check_champions(self) -> Tuple[str, Tone, str]:
        data = getattr(self.assets, "champ_data", None) or {}
        error = getattr(self.assets, "champion_data_error", "") or ""
        if data:
            return (
                "Loaded", Tone.SUCCESS,
                "{} champions from Data Dragon".format(len(data)),
            )
        if error:
            return ("Failed to load", Tone.DANGER, error)
        return (
            "Not loaded", Tone.WARNING,
            "Champion screens will be empty until this downloads.",
        )

    def _check_history(self) -> Tuple[str, Tone, str]:
        if self.db is None:
            return ("Unavailable", Tone.NEUTRAL, "No local database.")
        try:
            rows = self.db.get_recent_matches(limit=1) or []
        except Exception as exc:
            return ("Error", Tone.DANGER, str(exc))
        if rows:
            return ("Recording", Tone.SUCCESS, "Games are being saved locally.")
        return (
            "Nothing recorded yet", Tone.NEUTRAL,
            "Games are saved after they finish, with automation running.",
        )

    # ------------------------------------------------------------ details
    def _toggle_details(self) -> None:
        self._details_open = not self._details_open
        self.details_card.setVisible(self._details_open)
        self.btn_details.setText(
            "Hide developer details" if self._details_open
            else "Show developer details"
        )
        if self._details_open:
            self._render_metrics()

    def _render_metrics(self) -> None:
        lines = []
        try:
            from core.version import __version__

            lines.append("Version: {}".format(__version__))
        except Exception:
            pass

        if self.lcu is not None:
            try:
                hist = self.lcu.get_http_latency_histogram() or {}
                # Zeros on a fresh launch are meaningless; say so rather than
                # printing "0.0 ms" as though it were a measurement.
                samples = hist.get("count") or hist.get("samples") or 0
                if samples:
                    lines.append(
                        "LCU latency: {:.1f} ms average, {:.1f} ms p95 over {} calls"
                        .format(
                            hist.get("avg_latency_ms", 0.0),
                            hist.get("p95_latency_ms", 0.0),
                            samples,
                        )
                    )
                else:
                    lines.append("LCU latency: no requests recorded yet")
            except Exception as exc:
                lines.append("LCU latency: unavailable ({})".format(exc))

            try:
                ws = self.lcu.get_ws_telemetry() or {}
                lines.append(
                    "Websocket events: {}".format(ws.get("total_events", 0))
                )
            except Exception:
                pass

        try:
            from services.image_cache import ImageCacheService

            stats = ImageCacheService().get_disk_cache_stats() or {}
            lines.append(
                "Image cache: {} MB".format(stats.get("total_mb", 0.0))
            )
        except Exception:
            pass

        self.metrics_label.setText("\n".join(lines) or "Nothing to report.")

    # ------------------------------------------------------------ actions
    def report_text(self) -> str:
        """The whole page as plain text, for pasting into a bug report."""
        lines = ["LeagueLoop diagnostics", ""]
        for key, widget in self._checks:
            label = key.replace("_", " ").title()
            detail = widget.detail() if hasattr(widget, "detail") else ""
            lines.append(
                "{}: {}{}".format(
                    label, widget.text(), " — {}".format(detail) if detail else ""
                )
            )
        self._render_metrics()
        lines += ["", self.metrics_label.text()]
        return "\n".join(lines)

    def _on_copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.report_text())
            self.btn_copy.setText("Copied")
            self.btn_copy.setEnabled(False)
            from PySide6.QtCore import QTimer

            QTimer.singleShot(1500, self._reset_copy)

    def _reset_copy(self) -> None:
        self.btn_copy.setText("Copy report")
        self.btn_copy.setEnabled(True)

    def _on_prune(self) -> None:
        try:
            from services.image_cache import ImageCacheService

            ImageCacheService().clean_disk_cache()
        except Exception:
            pass
        self._render_metrics()
