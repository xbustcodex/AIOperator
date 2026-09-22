"""Experience memory: an append-only log of agent runs and outcomes."""

import json
import os
import time
from collections import Counter
from typing import Any, Optional


class ExperienceMemory:
    """Persistent, capped collection of experience records."""

    def __init__(self, memory_dir: str, capacity: int = 2000):
        self._path = os.path.join(memory_dir, "experience.jsonl")
        self._capacity = capacity
        os.makedirs(memory_dir, exist_ok=True)

    def record(self, entry: dict) -> None:
        row = {"ts": time.time(), **entry}
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        self._trim()

    def recall(self, limit: Optional[int] = None) -> list[dict]:
        entries = [json.loads(line) for line in self._lines()]
        if limit is not None:
            entries = entries[-limit:]
        return entries

    def count(self) -> int:
        return len(self._lines())

    def stats(self) -> dict:
        """Aggregate learning statistics over recorded experiences."""
        entries = self.recall()
        total = len(entries)
        if not total:
            return {"total": 0, "done": 0, "failed": 0, "success_rate": None,
                    "top_goals": [], "top_failures": []}

        def _bucket(value: Any, size: int = 60) -> str:
            text = str(value or "")
            return text[:size]

        statuses = Counter(entry.get("status") for entry in entries)
        done = statuses.get("done", 0)
        failed = statuses.get("failed", 0)
        goals = Counter(_bucket(entry.get("target")) for entry in entries)
        failures = Counter(
            _bucket(entry.get("error")) for entry in entries
            if entry.get("status") == "failed"
        )
        return {
            "total": total,
            "done": done,
            "failed": failed,
            "success_rate": round(done / total, 3) if total else None,
            "top_goals": goals.most_common(8),
            "top_failures": failures.most_common(8),
        }

    def clear(self) -> None:
        try:
            os.remove(self._path)
        except OSError:
            pass

    def _lines(self) -> list[str]:
        if not os.path.isfile(self._path):
            return []
        with open(self._path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    def _trim(self) -> None:
        lines = self._lines()
        if len(lines) <= self._capacity:
            return
        with open(self._path, "w", encoding="utf-8") as f:
            f.writelines(line + "\n" for line in lines[-self._capacity:])