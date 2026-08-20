"""
QtDiagnosticsTab — System Health & Developer Telemetry (UI/UX Master Plan §58).

Provides:
1. User-Facing System Health Panel:
   - League Client connection state & manual reconnect action
   - Automation engine status
   - Asset Manager / Data Dragon sync state & reload
   - Community aggregate stats scraper status
   - Last action / error readout
   - "Copy Diagnostics" for one-click bug report sharing
2. Developer Mode (collapsible telemetry):
   - HTTP latency histograms (Avg / P95)
   - WebSocket event throughput
   - Disk cache usage & pruning
   - Local SQLite match record inspector
"""
from __future__ import annotations

import platform
import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.badge import LLBadge
from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSeparator
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    GOLD_PRIMARY,
    SURFACE_APP_BACKGROUND,
    SURFACE_PANEL,
    SURFACE_SUNKEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.spacing import CONTENT_MARGIN, CONTROL_HEIGHT_MD, SPACE_LG, SPACE_MD, SPACE_SM, SPACE_XS
from ui.qt.theme.typography import TEXT_BODY, TEXT_BODY_STRONG, TEXT_CAPTION, TEXT_PAGE_TITLE
from services.image_cache import ImageCacheService


class QtDiagnosticsTab(QWidget):
    """System health overview and developer telemetry."""

    def __init__(self, container=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.container = container
        self.lcu = getattr(container, "lcu", None) if container else None
        self.db = getattr(container, "db", None) if container else None
        self.assets = getattr(container, "assets", None) if container else None
        self.image_cache = ImageCacheService()

        self._setup_ui()
        self.refresh_metrics()
        self.load_match_history()

        # 3-second live refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_metrics)
        self.timer.start(3000)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        # Header Title + Top Actions
        header_layout = QHBoxLayout()
        header = QLabel("Diagnostics & Health", self)
        header.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        header_layout.addWidget(header)
        header_layout.addStretch()

        self.btn_copy_diag = LLButton(
            "📋 Copy Diagnostics",
            variant=ButtonVariant.SECONDARY,
            size=ButtonSize.SM,
            parent=self,
        )
        self.btn_copy_diag.clicked.connect(self._on_copy_diagnostics)
        header_layout.addWidget(self.btn_copy_diag)

        root.addLayout(header_layout)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        body = QVBoxLayout(holder)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(SPACE_MD)

        # =====================================================================
        # 1. System Health Panel (§58)
        # =====================================================================
        health_card = LLCard(title="System Health", parent=holder)

        # LCU Status Row
        row_lcu = QHBoxLayout()
        row_lcu.setSpacing(SPACE_MD)
        self.status_lcu = LLStatus(
            "Client Disconnected", Tone.WARNING, "Waiting for League Client", parent=health_card
        )
        row_lcu.addWidget(self.status_lcu, 1)
        self.btn_reconnect = LLButton("Reconnect", variant=ButtonVariant.SECONDARY, size=ButtonSize.SM, parent=health_card)
        self.btn_reconnect.clicked.connect(self._on_reconnect)
        row_lcu.addWidget(self.btn_reconnect)
        health_card.add_layout(row_lcu)

        health_card.add_widget(LLSeparator(parent=health_card))

        # Automation Status Row
        row_auto = QHBoxLayout()
        row_auto.setSpacing(SPACE_MD)
        self.status_auto = LLStatus(
            "Automation Engine", Tone.NEUTRAL, "Checking status...", parent=health_card
        )
        row_auto.addWidget(self.status_auto, 1)
        health_card.add_layout(row_auto)

        health_card.add_widget(LLSeparator(parent=health_card))

        # Assets & Scraper Status Row
        row_assets = QHBoxLayout()
        row_assets.setSpacing(SPACE_MD)
        self.status_assets = LLStatus(
            "Game Assets (Data Dragon)", Tone.NEUTRAL, "Loading champions...", parent=health_card
        )
        row_assets.addWidget(self.status_assets, 1)
        self.btn_reload_assets = LLButton("Reload Assets", variant=ButtonVariant.SECONDARY, size=ButtonSize.SM, parent=health_card)
        self.btn_reload_assets.clicked.connect(self._on_reload_assets)
        row_assets.addWidget(self.btn_reload_assets)
        health_card.add_layout(row_assets)

        body.addWidget(health_card)

        # =====================================================================
        # 2. Developer Mode Telemetry (Collapsible)
        # =====================================================================
        dev_card = LLCard(title="Developer Mode & Telemetry", parent=holder)

        dev_toggle_row = QHBoxLayout()
        self.chk_dev_mode = QCheckBox("Enable Developer Telemetry", dev_card)
        self.chk_dev_mode.setStyleSheet(TEXT_BODY.qss(color=TEXT_PRIMARY))
        self.chk_dev_mode.toggled.connect(self._on_dev_mode_toggled)
        dev_toggle_row.addWidget(self.chk_dev_mode)
        dev_toggle_row.addStretch()

        self.btn_prune_cache = LLButton(
            "🧹 Prune Disk Cache",
            variant=ButtonVariant.SECONDARY,
            size=ButtonSize.SM,
            parent=dev_card,
        )
        self.btn_prune_cache.clicked.connect(self._on_prune_cache)
        dev_toggle_row.addWidget(self.btn_prune_cache)
        dev_card.add_layout(dev_toggle_row)

        self.dev_container = QWidget(dev_card)
        dev_layout = QVBoxLayout(self.dev_container)
        dev_layout.setContentsMargins(0, SPACE_SM, 0, 0)
        dev_layout.setSpacing(SPACE_MD)

        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(SPACE_SM)
        self.lbl_avg_latency = self._create_metric_card("AVG HTTP LATENCY", "0.0 ms", metrics_grid, 0, 0)
        self.lbl_p95_latency = self._create_metric_card("P95 LATENCY", "0.0 ms", metrics_grid, 0, 1)
        self.lbl_ws_events = self._create_metric_card("WS TOTAL EVENTS", "0", metrics_grid, 0, 2)
        self.lbl_disk_cache = self._create_metric_card("DISK CACHE SIZE", "0 MB", metrics_grid, 0, 3)
        self.lbl_stats_scraper = self._create_metric_card("STATS (LOLALYTICS)", "Ready", metrics_grid, 0, 4)
        dev_layout.addLayout(metrics_grid)

        # Match History Table Section
        table_title = QLabel("LOCAL MATCH HISTORY (SQLITE)", self.dev_container)
        table_title.setStyleSheet(TEXT_CAPTION.qss(color=TEXT_MUTED))
        dev_layout.addWidget(table_title)

        self.table = QTableWidget(self.dev_container)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Game ID", "Champion", "Result", "KDA", "Duration", "Queue"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setMinimumHeight(180)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {SURFACE_SUNKEN};
                border: 1px solid {BORDER_DEFAULT};
                gridline-color: {BORDER_DEFAULT};
                color: {TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {SURFACE_PANEL};
                color: {GOLD_PRIMARY};
                font-weight: bold;
                border: 1px solid {BORDER_DEFAULT};
                padding: 4px;
            }}
        """)
        dev_layout.addWidget(self.table)

        self.dev_container.setVisible(False)
        dev_card.add_widget(self.dev_container)

        body.addWidget(dev_card)
        body.addStretch(1)

        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

    def _create_metric_card(self, title: str, default_val: str, layout: QGridLayout, row: int, col: int) -> QLabel:
        box = QVBoxLayout()
        box.setSpacing(SPACE_XS)
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(TEXT_CAPTION.qss(color=TEXT_MUTED))
        v_lbl = QLabel(default_val)
        v_lbl.setStyleSheet(TEXT_BODY_STRONG.qss(color=GOLD_PRIMARY))
        box.addWidget(t_lbl)
        box.addWidget(v_lbl)
        layout.addLayout(box, row, col)
        return v_lbl

    def _on_dev_mode_toggled(self, checked: bool) -> None:
        self.dev_container.setVisible(checked)

    def _on_reconnect(self) -> None:
        if self.lcu and hasattr(self.lcu, "connect"):
            try:
                self.lcu.connect()
            except Exception:
                pass
        self.refresh_metrics()

    def _on_reload_assets(self) -> None:
        if self.assets and hasattr(self.assets, "start_loading"):
            try:
                self.assets.start_loading()
            except Exception:
                pass
        self.refresh_metrics()

    def refresh_metrics(self) -> None:
        """Fetch live health states and HTTP/WebSocket telemetry."""
        # 1. LCU Status
        connected = bool(self.lcu and getattr(self.lcu, "is_connected", False))
        if connected:
            self.status_lcu.set_status(
                "Client Connected",
                Tone.SUCCESS,
                f"Port {getattr(self.lcu, 'port', 'unknown')}",
            )
        else:
            self.status_lcu.set_status(
                "Client Disconnected",
                Tone.WARNING,
                "League of Legends client not detected",
            )

        # 2. Automation Status
        auto = getattr(self.container, "automation", None) if self.container else None
        if auto:
            running = getattr(auto, "is_running", False)
            paused = getattr(auto, "paused", False)
            if running and not paused:
                self.status_auto.set_status("Automation Running", Tone.SUCCESS, "Ready to handle lobby & champ select")
            elif running and paused:
                self.status_auto.set_status("Automation Paused", Tone.WARNING, "Temporarily paused by user")
            else:
                self.status_auto.set_status("Automation Idle", Tone.NEUTRAL, "Master switch enabled, waiting for events")
        else:
            self.status_auto.set_status("Automation Off", Tone.NEUTRAL, "Engine not active")

        # 3. Assets & Scraper Status
        if self.assets:
            champ_count = len(getattr(self.assets, "champ_data", {}) or {})
            if champ_count > 0:
                self.status_assets.set_status(
                    "Assets Loaded",
                    Tone.SUCCESS,
                    f"{champ_count} champions synced from Data Dragon",
                )
            else:
                self.status_assets.set_status(
                    "Assets Pending",
                    Tone.WARNING,
                    "Downloading champion metadata...",
                )

        scraper = getattr(self.container, "scraper", None) if self.container else None
        if scraper:
            try:
                mode = getattr(scraper, "mode", "ARAM")
                count = len(getattr(scraper, "win_rates", {}))
                self.lbl_stats_scraper.setText(f"{mode} ({count})")
            except Exception:
                pass

        # 4. Developer Metrics
        if self.lcu and self.chk_dev_mode.isChecked():
            try:
                hist = self.lcu.get_http_latency_histogram()
                self.lbl_avg_latency.setText(f"{hist.get('avg_latency_ms', 0.0):.1f} ms")
                self.lbl_p95_latency.setText(f"{hist.get('p95_latency_ms', 0.0):.1f} ms")
                ws_tel = self.lcu.get_ws_telemetry()
                self.lbl_ws_events.setText(str(ws_tel.get("total_events", 0)))
            except Exception:
                pass

        try:
            stats = self.image_cache.get_disk_cache_stats()
            self.lbl_disk_cache.setText(f"{stats.get('total_mb', 0.0):.1f} MB")
        except Exception:
            pass

    def _on_prune_cache(self) -> None:
        """Trigger disk cache cleanup."""
        try:
            self.image_cache.clean_disk_cache(max_files=100, max_bytes=20 * 1024 * 1024)
            self.refresh_metrics()
        except Exception:
            pass

    def _on_copy_diagnostics(self) -> None:
        """Format an actionable diagnostic summary to the system clipboard."""
        connected = bool(self.lcu and getattr(self.lcu, "is_connected", False))
        auto = getattr(self.container, "automation", None) if self.container else None
        champ_count = len(getattr(self.assets, "champ_data", {}) or {}) if self.assets else 0
        scraper = getattr(self.container, "scraper", None) if self.container else None

        report = [
            "### LeagueLoop Diagnostics Report",
            f"- **OS**: {platform.system()} {platform.release()} ({platform.machine()})",
            f"- **Python**: {sys.version.split()[0]}",
            f"- **LCU Connected**: {connected} (Port: {getattr(self.lcu, 'port', 'N/A')})",
            f"- **Automation Running**: {getattr(auto, 'is_running', False)} (Paused: {getattr(auto, 'paused', False)})",
            f"- **Champions Loaded**: {champ_count}",
            f"- **Scraper Mode**: {getattr(scraper, 'mode', 'None')} ({len(getattr(scraper, 'win_rates', {}))} entries)",
            f"- **Disk Cache**: {self.lbl_disk_cache.text()}",
        ]
        text = "\n".join(report)
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.btn_copy_diag.setText("✓ Copied!")
            QTimer.singleShot(2000, lambda: self.btn_copy_diag.setText("📋 Copy Diagnostics"))

    def load_match_history(self) -> None:
        """Populate SQLite local match history."""
        if not self.db:
            return

        try:
            matches = self.db.get_recent_matches(limit=20)
            self.table.setRowCount(len(matches))

            for row_idx, match in enumerate(matches):
                game_id = str(match.get("game_id", ""))
                champ = str(match.get("champion_name") or match.get("champion") or "")
                result = "WIN" if match.get("win") else "LOSS"
                kda = f"{match.get('kills', 0)}/{match.get('deaths', 0)}/{match.get('assists', 0)}"
                dur_s = match.get("duration_s") or match.get("duration_seconds", 0)
                duration = f"{dur_s // 60}m {dur_s % 60}s" if dur_s else "0m"
                queue = str(match.get("queue_id", ""))

                self.table.setItem(row_idx, 0, QTableWidgetItem(game_id))
                self.table.setItem(row_idx, 1, QTableWidgetItem(champ))
                res_item = QTableWidgetItem(result)
                res_item.setForeground(Qt.green if result == "WIN" else Qt.red)
                self.table.setItem(row_idx, 2, res_item)
                self.table.setItem(row_idx, 3, QTableWidgetItem(kda))
                self.table.setItem(row_idx, 4, QTableWidgetItem(duration))
                self.table.setItem(row_idx, 5, QTableWidgetItem(queue))
        except Exception:
            pass
