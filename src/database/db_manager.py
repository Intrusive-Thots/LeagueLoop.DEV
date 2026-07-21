"""
Database Manager Module
Handles SQLite relational database storage for settings, champion metadata, match history, and cache metadata.
"""
import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional
from utils.logger import Logger


class DatabaseManager:
    """Thread-safe SQLite database manager for application data."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            appdata = os.environ.get("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local"))
            db_dir = os.path.join(appdata, "LeagueLoop")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "leagueloop.db")

        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes database schema tables."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                # Settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Champions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS champions (
                        id INTEGER PRIMARY KEY,
                        key TEXT NOT NULL,
                        name TEXT NOT NULL,
                        tags TEXT,
                        win_rate REAL DEFAULT 0.0
                    )
                """)

                # History table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        champion_name TEXT NOT NULL,
                        role TEXT,
                        action TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Cache Metadata table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cache_metadata (
                        asset_key TEXT PRIMARY KEY,
                        version TEXT NOT NULL,
                        checksum TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.commit()
                conn.close()
                Logger.info("DatabaseManager", f"Database initialized cleanly at: {self.db_path}")
            except Exception as e:
                Logger.error("DatabaseManager", f"Failed to initialize database schema: {e}")

    def set_setting(self, key: str, value: Any):
        """Persists a key-value setting entry into the SQLite settings table."""
        with self._lock:
            try:
                val_json = json.dumps(value)
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                """, (key, val_json))
                conn.commit()
                conn.close()
            except Exception as e:
                Logger.error("DatabaseManager", f"Error setting key {key}: {e}")

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting entry from SQLite database."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    return json.loads(row["value"])
            except Exception as e:
                Logger.error("DatabaseManager", f"Error getting key {key}: {e}")
        return default

    def log_history(self, champion_name: str, role: str, action: str):
        """Logs pick/ban action history entry."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO history (champion_name, role, action)
                    VALUES (?, ?, ?)
                """, (champion_name, role, action))
                conn.commit()
                conn.close()
            except Exception as e:
                Logger.error("DatabaseManager", f"Error logging history: {e}")

    def get_recent_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent action history entries."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT champion_name, role, action, timestamp
                    FROM history
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                Logger.error("DatabaseManager", f"Error fetching history: {e}")
                return []


# Global singleton instance
_db_manager_instance: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Returns global DatabaseManager singleton instance."""
    global _db_manager_instance
    if _db_manager_instance is None:
        _db_manager_instance = DatabaseManager()
    return _db_manager_instance
