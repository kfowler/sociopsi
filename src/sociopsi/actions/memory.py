"""Memory persistence: journal and key-value storage."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sociopsi.types import JournalEntry


class Journal:
    """Append-only journal for recording experiences."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self, entry: str, mood: str | None = None, somatic_snapshot: str | None = None
    ) -> None:
        """Write an entry to the journal."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "entry": entry,
            "mood": mood,
            "somatic_snapshot": somatic_snapshot,
        }

        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def read(self, count: int = 10) -> list[JournalEntry]:
        """Read the most recent entries."""
        entries: list[JournalEntry] = []

        if not self.path.exists():
            return entries

        # Read all lines and take the last N
        with open(self.path) as f:
            lines = f.readlines()

        for line in lines[-count:]:
            try:
                data = json.loads(line.strip())
                entries.append(
                    JournalEntry(
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        entry=data["entry"],
                        mood=data.get("mood"),
                        somatic_snapshot=data.get("somatic_snapshot"),
                    )
                )
            except (json.JSONDecodeError, KeyError):
                continue

        return entries

    def search(self, query: str, limit: int = 10) -> list[JournalEntry]:
        """Search journal entries for a query string."""
        entries: list[JournalEntry] = []

        if not self.path.exists():
            return entries

        with open(self.path) as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if query.lower() in data["entry"].lower():
                        entries.append(
                            JournalEntry(
                                timestamp=datetime.fromisoformat(data["timestamp"]),
                                entry=data["entry"],
                                mood=data.get("mood"),
                                somatic_snapshot=data.get("somatic_snapshot"),
                            )
                        )
                        if len(entries) >= limit:
                            break
                except (json.JSONDecodeError, KeyError):
                    continue

        return entries


class MemoryStore:
    """Key-value memory store with persistence."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load memory from disk."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save(self) -> None:
        """Save memory to disk."""
        with open(self.path, "w") as f:
            json.dump(self._cache, f, indent=2, default=str)

    def store(self, key: str, value: Any) -> None:
        """Store a value."""
        self._cache[key] = {
            "value": value,
            "stored_at": datetime.now().isoformat(),
            "accessed_at": datetime.now().isoformat(),
        }
        self._save()

    def recall(self, key: str) -> Any | None:
        """Recall a value."""
        if key not in self._cache:
            return None

        # Update access time
        self._cache[key]["accessed_at"] = datetime.now().isoformat()
        self._save()

        return self._cache[key]["value"]

    def forget(self, key: str) -> bool:
        """Forget a value."""
        if key in self._cache:
            del self._cache[key]
            self._save()
            return True
        return False

    def list_keys(self) -> list[str]:
        """List all memory keys."""
        return list(self._cache.keys())
