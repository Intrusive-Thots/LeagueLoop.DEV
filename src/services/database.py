"""
Local SQLite database service for LeagueLoop.
Provides persistent storage for match history, champion performance statistics,
and session telemetry with WAL mode for concurrency and zero UI blocking.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from utils.logger import Logger
from utils.path_utils import get_data_dir

DB_PATH = os.path.join(get_data_dir(), "leagueloop.db")


class DatabaseService:
    """Thread-safe SQLite database service for match history and diagnostics."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns or creates the thread-safe connection."""
        if self._conn is None:
            # Ensure parent directory exists
            parent = os.path.dirname(self.db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=5.0,
            )
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode for high concurrency
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute("PRAGMA synchronous = NORMAL;")
            self._conn.execute("PRAGMA busy_timeout = 5000;")
        return self._conn

    def _init_db(self) -> None:
        """Initializes tables and indices."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS matches (
                        game_id INTEGER PRIMARY KEY,
                        timestamp REAL NOT NULL,
                        queue_id INTEGER,
                        champion_id INTEGER NOT NULL,
                        champion_name TEXT,
                        role TEXT,
                        win INTEGER NOT NULL,
                        kills INTEGER DEFAULT 0,
                        deaths INTEGER DEFAULT 0,
                        assists INTEGER DEFAULT 0,
                        duration_s INTEGER DEFAULT 0,
                        raw_json TEXT
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_champ ON matches(champion_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_ts ON matches(timestamp DESC);")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        phase TEXT,
                        latency_avg_ms REAL DEFAULT 0.0,
                        latency_p95_ms REAL DEFAULT 0.0,
                        ws_events_total INTEGER DEFAULT 0,
                        raw_json TEXT
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry_snapshots(timestamp DESC);")

    def record_match(self, match_data: Dict[str, Any]) -> bool:
        """
        Records or updates a completed match record.
        Expected keys: game_id, champion_id (required);
        Optional keys: queue_id, champion_name, role, win, kills, deaths, assists, duration_s, raw_json.
        """
        game_id = match_data.get("game_id")
        champ_id = match_data.get("champion_id")
        if game_id is None or champ_id is None:
            Logger.warning("DatabaseService", f"Cannot record match without game_id and champion_id: {match_data}")
            return False

        ts = match_data.get("timestamp", time.time())
        raw_json_str = json.dumps(match_data) if "raw_json" not in match_data else (
            match_data["raw_json"] if isinstance(match_data["raw_json"], str) else json.dumps(match_data["raw_json"])
        )

        with self._lock:
            try:
                conn = self._get_connection()
                with conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO matches (
                            game_id, timestamp, queue_id, champion_id, champion_name,
                            role, win, kills, deaths, assists, duration_s, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        int(game_id),
                        float(ts),
                        match_data.get("queue_id"),
                        int(champ_id),
                        match_data.get("champion_name", ""),
                        match_data.get("role", ""),
                        1 if match_data.get("win") else 0,
                        int(match_data.get("kills", 0)),
                        int(match_data.get("deaths", 0)),
                        int(match_data.get("assists", 0)),
                        int(match_data.get("duration_s", 0)),
                        raw_json_str,
                    ))
                return True
            except Exception as e:
                Logger.error("DatabaseService", f"Failed to record match {game_id}: {e}")
                return False

    def get_recent_matches(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves the most recent matches ordered by timestamp descending."""
        with self._lock:
            try:
                conn = self._get_connection()
                cur = conn.execute(
                    "SELECT * FROM matches ORDER BY timestamp DESC LIMIT ?",
                    (max(1, limit),)
                )
                return [dict(row) for row in cur.fetchall()]
            except Exception as e:
                Logger.error("DatabaseService", f"Failed to query recent matches: {e}")
                return []

    def get_match(self, game_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a single match by game ID."""
        with self._lock:
            try:
                conn = self._get_connection()
                cur = conn.execute("SELECT * FROM matches WHERE game_id = ?", (game_id,))
                row = cur.fetchone()
                return dict(row) if row else None
            except Exception as e:
                Logger.error("DatabaseService", f"Failed to query match {game_id}: {e}")
                return None

    def get_champion_stats(self, champion_id: Optional[int] = None) -> Dict[str, Any]:
        """Calculates win rate, average KDA, and total games for a specific champion or overall."""
        with self._lock:
            try:
                conn = self._get_connection()
                if champion_id is not None:
                    cur = conn.execute("""
                        SELECT 
                            COUNT(*) as games,
                            SUM(win) as wins,
                            AVG(kills) as avg_kills,
                            AVG(deaths) as avg_deaths,
                            AVG(assists) as avg_assists,
                            AVG(duration_s) as avg_duration_s
                        FROM matches
                        WHERE champion_id = ?
                    """, (champion_id,))
                else:
                    cur = conn.execute("""
                        SELECT 
                            COUNT(*) as games,
                            SUM(win) as wins,
                            AVG(kills) as avg_kills,
                            AVG(deaths) as avg_deaths,
                            AVG(assists) as avg_assists,
                            AVG(duration_s) as avg_duration_s
                        FROM matches
                    """)
                row = cur.fetchone()
                if not row or row["games"] == 0:
                    return {
                        "games": 0,
                        "wins": 0,
                        "losses": 0,
                        "win_rate_pct": 0.0,
                        "avg_kda": 0.0,
                        "avg_kills": 0.0,
                        "avg_deaths": 0.0,
                        "avg_assists": 0.0,
                    }

                games = row["games"]
                wins = row["wins"] or 0
                losses = games - wins
                win_rate = round((wins / games) * 100.0, 2)
                avg_k = row["avg_kills"] or 0.0
                avg_d = row["avg_deaths"] or 0.0
                avg_a = row["avg_assists"] or 0.0
                avg_kda = round((avg_k + avg_a) / max(1.0, avg_d), 2)

                return {
                    "games": games,
                    "wins": wins,
                    "losses": losses,
                    "win_rate_pct": win_rate,
                    "avg_kda": avg_kda,
                    "avg_kills": round(avg_k, 2),
                    "avg_deaths": round(avg_d, 2),
                    "avg_assists": round(avg_a, 2),
                }
            except Exception as e:
                Logger.error("DatabaseService", f"Failed to compute champion stats: {e}")
                return {"games": 0, "win_rate_pct": 0.0}

    def record_telemetry_snapshot(self, snapshot: Dict[str, Any]) -> bool:
        """Records a session diagnostics/telemetry snapshot."""
        ts = snapshot.get("timestamp", time.time())
        phase = snapshot.get("phase", "None")
        lat_avg = snapshot.get("latency_avg_ms", 0.0)
        lat_p95 = snapshot.get("latency_p95_ms", 0.0)
        ws_events = snapshot.get("ws_events_total", 0)
        raw_json_str = json.dumps(snapshot)

        with self._lock:
            try:
                conn = self._get_connection()
                with conn:
                    conn.execute("""
                        INSERT INTO telemetry_snapshots (
                            timestamp, phase, latency_avg_ms, latency_p95_ms, ws_events_total, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (float(ts), str(phase), float(lat_avg), float(lat_p95), int(ws_events), raw_json_str))
                return True
            except Exception as e:
                Logger.error("DatabaseService", f"Failed to record telemetry snapshot: {e}")
                return False

    def get_recent_telemetry(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent telemetry snapshots."""
        with self._lock:
            try:
                conn = self._get_connection()
                cur = conn.execute(
                    "SELECT * FROM telemetry_snapshots ORDER BY timestamp DESC LIMIT ?",
                    (max(1, limit),)
                )
                return [dict(row) for row in cur.fetchall()]
            except Exception as e:
                Logger.error("DatabaseService", f"Failed to query telemetry snapshots: {e}")
                return []

    def close(self) -> None:
        """Safely closes the SQLite connection."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
