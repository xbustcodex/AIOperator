"""Configuration system for Buster OS."""

import json
import os
from typing import Any, Optional


class ConfigError(Exception):
    pass


class Config:
    """Persistent JSON-backed configuration store.

    The configuration is materialized at ``~/.buster/config/config.json``
    by default and is the single source of truth for user-adjustable
    settings consumed by every Buster subsystem.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.expanduser("~/.buster/config/config.json")
        self._config: dict = {}
        self.load()

    def load(self) -> None:
        if not os.path.isfile(self.config_path):
            self._config = self.default_config()
            self.save()
        else:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                raise ConfigError(f"Failed to load config: {exc}") from exc

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value
        self.save()

    def get_nested(self, dotted_key: str, default: Any = None) -> Any:
        node = self._config
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set_nested(self, dotted_key: str, value: Any) -> None:
        parts = dotted_key.split(".")
        node = self._config
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        self.save()

    def all(self) -> dict:
        return dict(self._config)

    def default_config(self) -> dict:
        return {
            "logging_level": "INFO",
            "ai_providers": {},
            "permissions": {},
            "capabilities": {},
            "install_path": os.path.expanduser("~/.buster/"),
        }