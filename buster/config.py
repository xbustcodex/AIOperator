"""Configuration system for Buster OS."""

import json
import os
from typing import Any, Optional

from buster.install import (
    SYSTEM_CONFIG,
    default_config_path,
    install_from_config_path,
    resolve_install_path,
)


class ConfigError(Exception):
    pass


class Config:
    """Persistent JSON-backed configuration store.

    The configuration lives under the canonical install path
    (``<install>/config/config.json``) resolved by ``buster.install`` — the
    same single state authority used by bootstrap, the daemon, the GUI,
    busterctl, shell, services and doctor. ``install_path`` defaults to that
    same resolved location so no subsystem can drift onto a second path.
    """

    def __init__(self, config_path: Optional[str] = None,
                 install_path: Optional[str] = None):
        self.config_path = default_config_path(config_path)
        if config_path:
            if os.path.normcase(self.config_path) == os.path.normcase(SYSTEM_CONFIG):
                selected = install_path or resolve_install_path()
            else:
                selected = install_path or install_from_config_path(self.config_path)
        else:
            selected = install_path
        self.install_path = resolve_install_path(explicit=selected)
        self._config: dict = {}
        self.load()
        stored_install = self._config.get("install_path")
        self._config["install_path"] = self.install_path
        if not os.path.isfile(self.config_path) or stored_install != self.install_path:
            self.save()

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
        self._config["install_path"] = self.install_path
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if key == "install_path":
            value = self.install_path
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
        if dotted_key.split(".", 1)[0] == "install_path":
            value = self.install_path
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
            "install_path": self.install_path,
        }
