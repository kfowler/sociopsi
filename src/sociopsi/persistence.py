"""Drive state persistence with SQLite.

Provides save/restore lifecycle for drive states so the agent can resume
from where it left off after shutdown or crash. Uses SQLite WAL mode for
crash safety — incomplete writes are automatically rolled back on recovery.

Schema:
    drives(drive_id TEXT PK, archetype_id TEXT, state TEXT, updated_at TEXT)

Lifecycle:
    - save_drives() on shutdown
    - restore_drives() on startup
    - checkpoint() periodically (called by the drive system timer)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sociopsi.drives import Drive, DriveSystem

logger = logging.getLogger(__name__)

# Schema version for future migrations
_SCHEMA_VERSION = 1

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS drives (
    drive_id     TEXT PRIMARY KEY,
    archetype_id TEXT NOT NULL DEFAULT '',
    state        TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""

_CREATE_META = """\
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def _drive_to_state_json(drive: Drive) -> str:
    """Serialize a Drive's mutable state to JSON."""
    return json.dumps(
        {
            "demand": drive.demand,
            "satisfaction": drive.satisfaction,
            "delta": drive.delta,
            "urgency": drive.urgency,
            "last_value": drive.last_value,
            "reason": drive.reason,
        }
    )


def _apply_state_json(drive: Drive, state_json: str) -> None:
    """Restore mutable state from JSON onto a Drive instance."""
    data = json.loads(state_json)
    drive.demand = float(data.get("demand", drive.baseline))
    drive.satisfaction = float(data.get("satisfaction", 0.0))
    drive.delta = float(data.get("delta", 0.0))
    drive.urgency = float(data.get("urgency", 0.0))
    drive.last_value = float(data.get("last_value", 0.0))
    drive.reason = str(data.get("reason", ""))


class DriveStore:
    """SQLite-backed persistence for drive states.

    Thread-safe: the underlying connection uses WAL mode and all writes
    are serialized through a lock.  The periodic checkpoint is designed
    to be called from the drive system timer thread.

    Args:
        db_path: Path to the SQLite database file.
        checkpoint_interval: Seconds between automatic checkpoints.
            Set to 0 to disable periodic checkpoints.
    """

    def __init__(self, db_path: Path, checkpoint_interval: float = 30.0) -> None:
        self._db_path = db_path
        self._checkpoint_interval = checkpoint_interval
        self._lock = threading.Lock()
        self._last_checkpoint: float = 0.0

        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = self._connect()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with WAL mode for crash safety."""
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist and handle migrations."""
        with self._lock:
            self._conn.execute(_CREATE_TABLE)
            self._conn.execute(_CREATE_META)

            # Check schema version
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                    (str(_SCHEMA_VERSION),),
                )
            self._conn.commit()

    def save_drives(self, drive_system: DriveSystem) -> None:
        """Save all drive states to the database.

        Uses a single transaction — either all drives are saved or none.
        """
        now = _now_iso()
        with self._lock:
            try:
                with self._conn:
                    for name, drive in drive_system.drives.items():
                        state_json = _drive_to_state_json(drive)
                        self._conn.execute(
                            "INSERT OR REPLACE INTO drives "
                            "(drive_id, archetype_id, state, updated_at) "
                            "VALUES (?, ?, ?, ?)",
                            (name, "", state_json, now),
                        )
                self._last_checkpoint = time.monotonic()
                logger.debug("Saved %d drive states", len(drive_system.drives))
            except sqlite3.Error:
                logger.exception("Failed to save drive states")

    def restore_drives(self, drive_system: DriveSystem) -> bool:
        """Restore drive states from the database.

        Only restores drives that exist in both the database and the
        drive system — new drives get their defaults, removed drives
        are ignored.

        Returns:
            True if any drives were restored, False otherwise.
        """
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT drive_id, state, updated_at FROM drives"
                ).fetchall()
            except sqlite3.Error:
                logger.exception("Failed to read drive states")
                return False

        if not rows:
            logger.debug("No persisted drive states found")
            return False

        restored = 0
        for drive_id, state_json, _updated_at in rows:
            if drive_id in drive_system.drives:
                try:
                    _apply_state_json(drive_system.drives[drive_id], state_json)
                    restored += 1
                except (json.JSONDecodeError, KeyError, ValueError):
                    logger.warning("Corrupt state for drive %s, using defaults", drive_id)

        logger.info(
            "Restored %d/%d drive states (saved %s)",
            restored,
            len(rows),
            rows[0][2] if rows else "never",
        )
        return restored > 0

    def maybe_checkpoint(self, drive_system: DriveSystem) -> bool:
        """Save drives if enough time has passed since last checkpoint.

        Designed to be called frequently (e.g. every timer tick). The
        actual write only happens when checkpoint_interval has elapsed.

        Returns:
            True if a checkpoint was performed.
        """
        if self._checkpoint_interval <= 0:
            return False
        now = time.monotonic()
        if now - self._last_checkpoint < self._checkpoint_interval:
            return False
        self.save_drives(drive_system)
        return True

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                logger.exception("Error closing drive store")

    def wipe(self) -> None:
        """Delete all persisted drive data. Useful for tests."""
        with self._lock:
            try:
                with self._conn:
                    self._conn.execute("DELETE FROM drives")
                logger.debug("Wiped all persisted drive states")
            except sqlite3.Error:
                logger.exception("Failed to wipe drive states")
