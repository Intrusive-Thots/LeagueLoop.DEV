"""
PySide6 Diagnostics Tab Widget for LeagueLoop.
Provides real-time telemetry metrics, SQLite match history, and asset cache diagnostics.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.qt.theme import (
    COLOR_BACKGROUND_CARD,
    COLOR_BACKGROUND_DARK,
    COLOR_BACKGROUND_PANEL,
    COLOR_BLUE_ACCENT,
    COLOR_BORDER,
    COLOR_BORDER_GOLD,
    COLOR_GOLD_PRIMARY,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)
from services.image_cache import ImageCacheService


class QtDiagnosticsTab(QWidget):
    """Real-time telemetry and database match history inspection tab."""

    def __init__(self, container=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.container = container
        self.lcu = container.lcu if container else None
        self.db = container.db if container else None
        self.image_cache = ImageCacheService()

        self._setup_ui()
        self.refresh_metrics()
        self.load_match_history()

        # 3-second live refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_metrics)
        self.timer.start(3000)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header Title
        header_layout = QHBoxLayout()
        header = QLabel("System Diagnostics & Telemetry", self)
        header.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {COLOR_GOLD_PRIMARY};
        """)
        header_layout.addWidget(header)
        header_layout.addStretch()

        self.btn_prune_cache = QPushButton("🧹 Prune Cache", self)
        self.btn_prune_cache.clicked.connect(self._on_prune_cache)
        header_layout.addWidget(self.btn_prune_cache)

        layout.addLayout(header_layout)

        # Telemetry Metric Cards
        metrics_card = QFrame(self)
        metrics_card.setObjectName("panel")
        metrics_layout = QGridLayout(metrics_card)
        metrics_layout.setContentsMargins(16, 16, 16, 16)
        metrics_layout.setSpacing(16)

        self.lbl_avg_latency = self._create_metric_card("AVG HTTP LATENCY", "0.0 ms", metrics_layout, 0, 0)
        self.lbl_p95_latency = self._create_metric_card("P95 LATENCY", "0.0 ms", metrics_layout, 0, 1)
        self.lbl_ws_events = self._create_metric_card("WS TOTAL EVENTS", "0", metrics_layout, 0, 2)
        self.lbl_disk_cache = self._create_metric_card("DISK CACHE SIZE", "0 MB", metrics_layout, 0, 3)

        layout.addWidget(metrics_card)

        # Match History Table Section
        table_title = QLabel("LOCAL MATCH HISTORY (SQLITE)", self)
        table_title.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        layout.addWidget(table_title)

        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Game ID", "Champion", "Result", "KDA", "Duration", "Queue"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLOR_BACKGROUND_PANEL};
                border: 1px solid {COLOR_BORDER};
                gridline-color: {COLOR_BORDER};
                color: {COLOR_TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {COLOR_BACKGROUND_DARK};
                color: {COLOR_GOLD_PRIMARY};
                font-weight: bold;
                border: 1px solid {COLOR_BORDER};
                padding: 4px;
            }}
        """)
        layout.addWidget(self.table)

    def _create_metric_card(self, title: str, default_val: str, layout: QGridLayout, row: int, col: int) -> QLabel:
        box = QVBoxLayout()
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px; font-weight: bold;")
        v_lbl = QLabel(default_val)
        v_lbl.setStyleSheet(f"color: {COLOR_BLUE_ACCENT}; font-size: 18px; font-weight: bold;")
        box.addWidget(t_lbl)
        box.addWidget(v_lbl)
        layout.addLayout(box, row, col)
        return v_lbl

    def refresh_metrics(self) -> None:
        """Fetch live HTTP and WebSocket telemetry metrics."""
        if self.lcu:
            try:
                hist = self.lcu.get_http_latency_histogram()
                self.lbl_avg_latency.setText(f"{hist.get('avg_latency_ms', 0.0):.1f} ms")
                self.lbl_p95_latency.setText(f"{hist.get('p95_latency_ms', 0.0):.1f} ms")
                ws_tel = self.lcu.get_ws_telemetry()
                self.lbl_ws_events.setText(str(ws_tel.get("total_events", 0)))
            except Exception:
                pass

        try:
            disk_stats = self.image_cache.get_disk_cache_stats()
            self.lbl_disk_cache.setText(f"{disk_stats.get('total_mb', 0.0)} MB")
        except Exception:
            pass

    def load_match_history(self) -> None:
        """Load recent match history records from SQLite database."""
        if not self.db:
            return
        matches = self.db.get_recent_matches(limit=25)
        self.table.setRowCount(len(matches))

        for row_idx, m in enumerate(matches):
            win_str = "WIN" if m.get("win") else "LOSS"
            kda_str = f"{m.get('kills', 0)}/{m.get('deaths', 0)}/{m.get('assists', 0)}"
            dur_min = m.get("duration_s", 0) // 60
            dur_sec = m.get("duration_s", 0) % 60
            dur_str = f"{dur_min}m {dur_sec}s"

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(m.get("game_id", ""))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(m.get("champion_name", ""))))
            
            res_item = QTableWidgetItem(win_str)
            res_item.setForeground(Qt.green if m.get("win") else Qt.red)
            self.table.setItem(row_idx, 2, res_item)

            self.table.setItem(row_idx, 3, QTableWidgetItem(kda_str))
            self.table.setItem(row_idx, 4, QTableWidgetItem(dur_str))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(m.get("queue_id", ""))))

    def _on_prune_cache(self) -> None:
        self.image_cache.clean_disk_cache(max_files=100, max_bytes=20 * 1024 * 1024)
        self.refresh_metrics()
