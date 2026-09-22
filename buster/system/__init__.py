"""Buster OS system integration helpers (used on the built Linux system)."""

import os

SYSTEM_INSTALL = "/var/lib/buster"
SYSTEM_LOG_DIR = "/var/log/buster"
SYSTEM_CONFIG = "/etc/buster/config.json"


def system_install_path() -> str:
    return os.environ.get("BUSTER_INSTALL", SYSTEM_INSTALL)


def system_log_dir() -> str:
    return os.environ.get("BUSTER_LOG_DIR", SYSTEM_LOG_DIR)


def system_config_path() -> str:
    return os.environ.get("BUSTER_CONFIG", SYSTEM_CONFIG)


def prepare_env() -> None:
    """Set system defaults for Buster OS without overriding user values."""
    os.environ.setdefault("BUSTER_INSTALL", SYSTEM_INSTALL)
    os.environ.setdefault("BUSTER_LOG_DIR", SYSTEM_LOG_DIR)
    os.environ.setdefault("BUSTER_CONFIG", SYSTEM_CONFIG)