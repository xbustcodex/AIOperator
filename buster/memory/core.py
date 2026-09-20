"""JSON-backed memory store for Buster OS.

A lightweight, dependency-free persistent key/value memory with optional
expiry. Suitable for the resource-constrained Termux environment while a
more advanced vector store can be swapped in later through the same API.
"""

import json
import logging
import os
import time
from typing import Any, Optional


class Memory:
    """Persistent JSON memory with TTL support."""

    def __init__(self, memory_dir: str):
        os.makedirs(memory_dir, exist_ok=True)
        self._path = os.path.join(memory_dir, "memory.json")
        self._data: dict = {}
        self.logger = logging.getLogger("buster.memory")
        self._load()

    def _load(self) -> None:
        if os.path.isfile(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.logger.warning("Memory file unreadable; starting empty")
                self._data = {}

    def _save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            self.logger.exception("Failed to persist memory")

    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expires = (time.time() + ttl) if ttl is not None else None
        self._data[key] = {"value": value, "expires": expires}
        self._save()

    def get(self, key: str, default: Any = None) -> Any:
        entry = self._data.get(key)
        if entry is None:
            return default
        expires = entry.get("expires")
        if expires is not None and time.time() > expires:
            self._data.pop(key, None)
            self._save()
            return default
        return entry.get("value", default)

    def delete(self, key: str) -> bool:
        existed = key in self._data
        if existed:
            del self._data[key]
            self._save()
        return existed

    def keys(self) -> list[str]:
        now = time.time()
        return [k for k, e in self._data.items()
                if e.get("expires") is None or now <= e["expires"]]

    def clear(self) -> None:
        self._data.clear()
        self._save()