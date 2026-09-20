"""Audit trail for Buster OS.

Appends structured, timestamped records of significant system actions into
a JSON-lines audit log, forming the tamper-observable history of the
environment.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Optional


class Audit:
    """Append-only JSON-lines audit recorder."""

    def __init__(self, log_dir: str, max_bytes: int = 10 * 1024 * 1024):
        self._path = os.path.join(log_dir, "audit.jsonl")
        self._max_bytes = max_bytes
        self._lock = threading.Lock()
        self.logger = logging.getLogger("buster.kernel.audit")

    def record(self, action: str, actor: str, detail: Optional[dict] = None) -> None:
        entry = {
            "ts": time.time(),
            "action": action,
            "actor": actor,
            "detail": detail or {},
        }
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self._path), exist_ok=True)
                if os.path.isfile(self._path) and os.path.getsize(self._path) > self._max_bytes:
                    self._rotate()
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
            except OSError:
                self.logger.exception("Audit write failed for action '%s'", action)

    def tail(self, limit: int = 20) -> list[dict]:
        entries: list[dict] = []
        if not os.path.isfile(self._path):
            return entries
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-limit:]

    def _rotate(self) -> None:
        rotated = f"{self._path}.{int(time.time())}"
        try:
            os.replace(self._path, rotated)
        except OSError:
            self.logger.error("Audit rotation failed")