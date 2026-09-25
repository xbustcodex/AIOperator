"""Canonical Buster install/state-path resolution.

One authority decides where a Buster install lives, and every client that
needs runtime state uses it: CLI, daemon, RuntimeLock/RuntimeClient,
RemoteKernel, GUI, busterctl, shell, services, doctor, bootstrap and
update/migration machinery. Introducing competing path authorities here
would recreate the v0.4.0 defect where ``buster bootstrap`` created
``/root/.buster`` while ``buster-gui``/``busterctl`` looked at
``/var/lib/buster``.

Resolution order (first match wins):

1. An explicit caller-provided path (e.g. ``--install-path``).
2. ``$BUSTER_INSTALL``.
3. The system configuration ``/etc/buster/config.json`` — the system-deployed
   Buster OS layout (canonical system install is ``/var/lib/buster``).
4. The development/user configuration ``~/.buster/config/config.json``.
5. The development default ``~/.buster``.

The resolved directory is the single state authority: runtime lock, RPC,
heartbeat, memory, configuration, logs and the daemon all live under it.
"""

import json
import os

SYSTEM_CONFIG = "/etc/buster/config.json"
SYSTEM_INSTALL = "/var/lib/buster"
SYSTEM_LOG_DIR = "/var/log/buster"

DEFAULT_USER_INSTALL = os.path.expanduser("~/.buster")
USER_CONFIG = os.path.join(DEFAULT_USER_INSTALL, "config", "config.json")


def resolve_install_path(explicit=None) -> str:
    """Resolve the one canonical install/state path for this environment."""
    if explicit:
        return os.path.abspath(os.path.expanduser(str(explicit)))
    env = os.environ.get("BUSTER_INSTALL")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    for candidate in (SYSTEM_CONFIG, USER_CONFIG):
        value = _config_install_path(candidate)
        if value:
            return os.path.abspath(value)
    return os.path.abspath(DEFAULT_USER_INSTALL)


def default_config_path(config_path=None) -> str:
    """Canonical config file location for the resolved install."""
    if config_path:
        return os.path.abspath(os.path.expanduser(config_path))
    return os.path.join(resolve_install_path(), "config", "config.json")


def install_from_config_path(config_path: str) -> str:
    """Infer the state root that owns an explicitly selected config file."""
    path = os.path.abspath(os.path.expanduser(str(config_path)))
    parent = os.path.dirname(path)
    if os.path.basename(parent).lower() == "config":
        return os.path.dirname(parent)
    return parent


def canonical_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(str(path))).rstrip(os.sep) or os.sep


def _config_install_path(config_path: str):
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        value = data.get("install_path")
        if value:
            value = os.path.expanduser(str(value))
            if not os.path.isabs(value):
                value = os.path.join(os.path.dirname(config_path), value)
            return value
    except (OSError, ValueError):
        return None
    return None