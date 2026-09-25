"""Buster OS system integration helpers (used on the built Linux system)."""

import os

from buster.install import (
    SYSTEM_CONFIG,
    SYSTEM_LOG_DIR,
    resolve_install_path,
)

SYSTEM_LOG_DIR = SYSTEM_LOG_DIR


def system_install_path() -> str:
    """Canonical system install path (same resolver as every other client)."""
    return resolve_install_path()


def system_log_dir() -> str:
    return os.environ.get("BUSTER_LOG_DIR", SYSTEM_LOG_DIR)


def system_config_path() -> str:
    return os.environ.get("BUSTER_CONFIG", SYSTEM_CONFIG)


def on_deployed_system() -> bool:
    """True when running from a deployed Buster OS rootfs (not a dev host)."""
    return (
        os.path.isfile(SYSTEM_CONFIG)
        or os.path.isfile("/usr/share/buster/VERSION")
        or os.path.isfile("/opt/buster/lib/buster/version.py")
    )


def prepare_env() -> None:
    """Set system defaults for Buster OS without overriding user values.

    Defaults are only injected when a deployed Buster OS system layout is
    present; on a development/user installation the canonical resolver keeps
    authority so ``~/.buster`` style installs are never hijacked.
    """
    if not on_deployed_system():
        return
    os.environ.setdefault("BUSTER_INSTALL", resolve_install_path())
    os.environ.setdefault("BUSTER_LOG_DIR", SYSTEM_LOG_DIR)
    os.environ.setdefault("BUSTER_CONFIG", SYSTEM_CONFIG)