"""Learned knowledge memory: facts with confidence and provenance."""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class KnowledgeEntry:
    key: str
    value: Any
    source: str = "system"
    confidence: float = 0.5
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)


class KnowledgeMemory:
    """Persistent store of distilled facts (learned knowledge)."""

    def __init__(self, memory_dir: str):
        self._path = os.path.join(memory_dir, "knowledge.json")
        self._entries: dict[str, KnowledgeEntry] = {}
        os.makedirs(memory_dir, exist_ok=True)
        self._load()

    def learn(self, key: str, value: Any, source: str = "system",
              confidence: float = 0.5) -> None:
        existing = self._entries.get(key)
        if existing is None or confidence >= existing.confidence:
            self._entries[key] = KnowledgeEntry(
                key=key, value=value, source=source,
                confidence=confidence, updated=time.time(),
            )
        self._save()

    def recall(self, key: str, default: Any = None) -> Any:
        entry = self._entries.get(key)
        return entry.value if entry else default

    def entries(self) -> list[dict]:
        return [{"key": e.key, "value": e.value, "source": e.source,
                 "confidence": e.confidence, "created": e.created,
                 "updated": e.updated} for e in self._entries.values()]

    def keys(self) -> list[str]:
        return sorted(self._entries.keys())

    def search(self, prefix: str = "", limit: Optional[int] = None) -> list[dict]:
        """Return entries whose key starts with ``prefix`` (newest first)."""
        matches = [
            e for e in self._entries.values()
            if e.key.startswith(prefix)
        ]
        matches.sort(key=lambda e: e.updated, reverse=True)
        if limit is not None:
            matches = matches[:limit]
        return [{"key": e.key, "value": e.value, "source": e.source,
                 "confidence": e.confidence, "updated": e.updated}
                for e in matches]

    def clear(self) -> None:
        self._entries.clear()
        self._save()

    def _load(self) -> None:
        if os.path.isfile(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                for row in rows:
                    entry = KnowledgeEntry(**{
                        "key": row["key"], "value": row["value"],
                        "source": row.get("source", "system"),
                        "confidence": row.get("confidence", 0.5),
                        "created": row.get("created", time.time()),
                        "updated": row.get("updated", time.time()),
                    })
                    self._entries[entry.key] = entry
            except (json.JSONDecodeError, OSError):
                self._entries = {}

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump([e.__dict__ for e in self._entries.values()], f, indent=2)