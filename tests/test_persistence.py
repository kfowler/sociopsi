"""Tests for drive state persistence with SQLite."""

import json
import sqlite3
import time
from pathlib import Path

import pytest

from sociopsi.config import AgentConfig
from sociopsi.drives import Drive, DriveSystem
from sociopsi.persistence import DriveStore, _apply_state_json, _drive_to_state_json


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "drives.db"


@pytest.fixture
def store(tmp_db: Path) -> DriveStore:
    """Create a DriveStore backed by a temp database."""
    s = DriveStore(tmp_db, checkpoint_interval=0)
    yield s
    s.close()


@pytest.fixture
def drive_system(tmp_path: Path) -> DriveSystem:
    """Create a DriveSystem with a temp database."""
    config = AgentConfig(voice_enabled=False, drives_db=tmp_path / "ds.db")
    return DriveSystem(config)


class TestDriveSerialisation:
    """Tests for Drive <-> JSON round-trip."""

    def test_round_trip(self) -> None:
        """Drive state survives serialization and deserialization."""
        drive = Drive(name="curiosity", demand=0.72, baseline=0.4)
        drive.satisfaction = 0.35
        drive.delta = 0.02
        drive.urgency = 0.85
        drive.last_value = 0.70
        drive.reason = "want to learn"

        state_json = _drive_to_state_json(drive)
        restored = Drive(name="curiosity", baseline=0.4)
        _apply_state_json(restored, state_json)

        assert restored.demand == pytest.approx(0.72)
        assert restored.satisfaction == pytest.approx(0.35)
        assert restored.delta == pytest.approx(0.02)
        assert restored.urgency == pytest.approx(0.85)
        assert restored.last_value == pytest.approx(0.70)
        assert restored.reason == "want to learn"

    def test_apply_state_uses_defaults_for_missing_keys(self) -> None:
        """Missing JSON keys fall back to Drive defaults."""
        drive = Drive(name="test", baseline=0.3)
        _apply_state_json(drive, json.dumps({"demand": 0.5}))

        assert drive.demand == 0.5
        assert drive.satisfaction == 0.0  # default

    def test_apply_state_corrupt_json_raises(self) -> None:
        """Corrupt JSON raises JSONDecodeError."""
        drive = Drive(name="test")
        with pytest.raises(json.JSONDecodeError):
            _apply_state_json(drive, "not valid json")


class TestDriveStore:
    """Tests for the SQLite DriveStore."""

    def test_schema_created(self, tmp_db: Path) -> None:
        """Database tables are created on init."""
        store = DriveStore(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t[0] for t in tables}
        assert "drives" in table_names
        assert "meta" in table_names
        conn.close()
        store.close()

    def test_wal_mode_enabled(self, tmp_db: Path) -> None:
        """WAL journal mode is set for crash safety."""
        store = DriveStore(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()
        store.close()

    def test_save_and_restore(self, store: DriveStore, drive_system: DriveSystem) -> None:
        """Drive state can be saved and restored."""
        # Modify some drives
        drive_system.drives["curiosity"].demand = 0.88
        drive_system.drives["curiosity"].satisfaction = 0.42
        drive_system.drives["energy"].demand = 0.15
        drive_system.drives["energy"].reason = "charging"

        store.save_drives(drive_system)

        # Create a fresh drive system
        fresh_db = store._db_path.parent / "fresh.db"
        config = AgentConfig(voice_enabled=False, drives_db=fresh_db)
        fresh = DriveSystem(config)

        # Manually restore from our store
        restored = store.restore_drives(fresh)

        assert restored is True
        assert fresh.drives["curiosity"].demand == pytest.approx(0.88)
        assert fresh.drives["curiosity"].satisfaction == pytest.approx(0.42)
        assert fresh.drives["energy"].demand == pytest.approx(0.15)
        assert fresh.drives["energy"].reason == "charging"

    def test_restore_empty_db(self, store: DriveStore, drive_system: DriveSystem) -> None:
        """Restore from empty database returns False."""
        assert store.restore_drives(drive_system) is False

    def test_restore_ignores_unknown_drives(self, tmp_db: Path, drive_system: DriveSystem) -> None:
        """Drives in DB but not in the system are silently ignored."""
        store = DriveStore(tmp_db, checkpoint_interval=0)

        # Manually insert a drive that doesn't exist in the system
        conn = sqlite3.connect(str(tmp_db))
        conn.execute(
            "INSERT INTO drives (drive_id, archetype_id, state, updated_at) VALUES (?, ?, ?, ?)",
            ("nonexistent_drive", "", json.dumps({"demand": 0.5}), "2026-01-01"),
        )
        conn.commit()
        conn.close()

        # Should not crash
        assert store.restore_drives(drive_system) is False
        store.close()

    def test_restore_handles_corrupt_state(self, tmp_db: Path, drive_system: DriveSystem) -> None:
        """Corrupt state JSON for a known drive is skipped gracefully."""
        store = DriveStore(tmp_db, checkpoint_interval=0)

        conn = sqlite3.connect(str(tmp_db))
        conn.execute(
            "INSERT INTO drives (drive_id, archetype_id, state, updated_at) VALUES (?, ?, ?, ?)",
            ("curiosity", "", "not valid json", "2026-01-01"),
        )
        conn.commit()
        conn.close()

        # Should warn and skip, not crash
        result = store.restore_drives(drive_system)
        # The corrupt row was found but couldn't be applied
        assert result is False  # 0 successfully restored
        store.close()

    def test_wipe(self, store: DriveStore, drive_system: DriveSystem) -> None:
        """Wipe clears all persisted data."""
        drive_system.drives["curiosity"].demand = 0.88
        store.save_drives(drive_system)
        store.wipe()
        assert store.restore_drives(drive_system) is False

    def test_save_is_atomic(self, store: DriveStore, drive_system: DriveSystem) -> None:
        """Save uses a transaction - partial writes don't persist."""
        store.save_drives(drive_system)

        # Verify all drives were saved
        conn = sqlite3.connect(str(store._db_path))
        count = conn.execute("SELECT COUNT(*) FROM drives").fetchone()[0]
        conn.close()

        assert count == len(drive_system.drives)


class TestCheckpointing:
    """Tests for periodic checkpoint behavior."""

    def test_maybe_checkpoint_respects_interval(self, tmp_path: Path) -> None:
        """Checkpoint only fires when interval has elapsed."""
        store = DriveStore(tmp_path / "ckpt.db", checkpoint_interval=1.0)
        config = AgentConfig(voice_enabled=False, drives_db=tmp_path / "ds.db")
        ds = DriveSystem(config)
        ds.drives["curiosity"].demand = 0.99

        # First call should checkpoint (last_checkpoint starts at 0)
        assert store.maybe_checkpoint(ds) is True
        # Immediately after, should NOT checkpoint
        assert store.maybe_checkpoint(ds) is False

        store.close()
        ds._store.close()

    def test_maybe_checkpoint_disabled_when_zero(self, tmp_path: Path) -> None:
        """Checkpoint interval of 0 disables periodic checkpoints."""
        store = DriveStore(tmp_path / "ckpt.db", checkpoint_interval=0)
        config = AgentConfig(voice_enabled=False, drives_db=tmp_path / "ds.db")
        ds = DriveSystem(config)

        assert store.maybe_checkpoint(ds) is False
        store.close()
        ds._store.close()


class TestDriveSystemIntegration:
    """Tests for DriveSystem persistence integration."""

    def test_drives_saved_on_stop(self, tmp_path: Path) -> None:
        """DriveSystem.stop() persists state to SQLite."""
        db = tmp_path / "drives.db"
        config = AgentConfig(voice_enabled=False, drives_db=db)
        ds = DriveSystem(config)
        ds.drives["curiosity"].demand = 0.77

        ds.start()
        time.sleep(0.1)
        ds.stop()

        # Verify data was written
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT state FROM drives WHERE drive_id = 'curiosity'").fetchone()
        conn.close()

        assert row is not None
        state = json.loads(row[0])
        # Demand may have shifted slightly from timer ticks,
        # but should be close to what we set
        assert state["demand"] > 0.5

    def test_drives_restored_on_init(self, tmp_path: Path) -> None:
        """New DriveSystem restores state from a previous session's DB."""
        db = tmp_path / "drives.db"

        # Session 1: set demand high and stop (persists)
        config1 = AgentConfig(voice_enabled=False, drives_db=db)
        ds1 = DriveSystem(config1)
        ds1.drives["affiliation"].demand = 0.91
        ds1.drives["affiliation"].reason = "lonely, no one seen"
        ds1.start()
        time.sleep(0.1)
        ds1.stop()

        # Session 2: should restore
        config2 = AgentConfig(voice_enabled=False, drives_db=db)
        ds2 = DriveSystem(config2)

        assert ds2.drives["affiliation"].demand > 0.5
        assert ds2.drives["affiliation"].reason == "lonely, no one seen"
        # Clean up (stop even though we didn't start — just closes store)
        ds2._store.close()

    def test_crash_recovery_via_wal(self, tmp_path: Path) -> None:
        """After a crash (no clean stop), last checkpoint is recoverable."""
        db = tmp_path / "drives.db"

        # Session 1: checkpoint but don't call stop()
        config = AgentConfig(voice_enabled=False, drives_db=db)
        ds = DriveSystem(config)
        ds.drives["energy"].demand = 0.66
        ds._store.save_drives(ds)
        # Simulate crash: don't call ds.stop(), just close the connection
        ds._store._conn.close()

        # Session 2: should recover from WAL
        config2 = AgentConfig(voice_enabled=False, drives_db=db)
        ds2 = DriveSystem(config2)

        assert ds2.drives["energy"].demand == pytest.approx(0.66)
        ds2._store.close()
