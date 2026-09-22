"""Migration from Buster v0.2.0 into the Buster OS system layout.

The v0.2.0 deployment kept persistent state under ``~/.buster``. Buster OS as
a system places persistent state under ``/var/lib/buster``. This module copies
the *persistent* v0.2.0 state (memories, knowledge, experience, goals, plans,
suggestions, configuration seeds) into the system layout without touching the
replaceable runtime files, and marks the identity so migration is idempotent.
"""

import json
import logging
import os
import shutil
import time

log = logging.getLogger("buster.osbuild.migrate")

_V02_STATE_DIRS = ("memory",)
_V02_STATE_FILES = (
    "state/goals.json",
    "state/plans.json",
    "state/suggestions.json",
)
CONFIG_FILE = "config/config.json"


def find_v02_install(base: str | None = None) -> str:
    return base or os.path.expanduser("~/.buster")


def migrate_v02(source: str | None = None,
                dest: str = "/var/lib/buster",
                force: bool = False) -> dict:
    source = find_v02_install(source)
    os.makedirs(dest, exist_ok=True)

    identity_file = os.path.join(dest, "identity.json")
    if os.path.isfile(identity_file) and not force:
        return {"migrated": False, "reason": "already migrated",
                "identity": _read_json(identity_file)}

    report = {"migrated": True, "from": source, "to": dest,
              "copied": [], "skipped": []}
    if not os.path.isdir(source):
        report["migrated"] = False
        report["reason"] = "no v0.2.0 install found"
        return report

    # memory stores
    memory_src = os.path.join(source, "memory")
    memory_dst = os.path.join(dest, "memory")
    os.makedirs(memory_dst, exist_ok=True)
    for name in ("memory.json", "knowledge.json", "experience.jsonl",
                 "episodic.jsonl", "procedural.json"):
        src_file = os.path.join(memory_src, name)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, os.path.join(memory_dst, name))
            report["copied"].append(f"memory/{name}")

    # goals / plans / suggestions
    state_dst = os.path.join(dest, "state")
    os.makedirs(state_dst, exist_ok=True)
    for rel in _V02_STATE_FILES:
        src_file = os.path.join(source, rel)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, os.path.join(dest, rel))
            report["copied"].append(rel)

    # configuration seed (permissions and provider seeds, not replaceable)
    config_src = os.path.join(source, CONFIG_FILE)
    if os.path.isfile(config_src):
        cfg_dst_dir = os.path.join(dest, "config")
        os.makedirs(cfg_dst_dir, exist_ok=True)
        shutil.copy2(config_src, os.path.join(dest, "config", "config.seed.json"))
        report["copied"].append("config/config.seed.json")

    # identity marker
    with open(identity_file, "w", encoding="utf-8") as handle:
        json.dump({
            "from": "buster-v0.2.0", "to": "buster-os-system",
            "migrated_at": time.time(),
            "install_dir": dest,
        }, handle, indent=2)
    report["identity"] = _read_json(identity_file)
    return report


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def system_install_path() -> str:
    """Default system state directory for Buster OS."""
    return os.environ.get("BUSTER_INSTALL", "/var/lib/buster")