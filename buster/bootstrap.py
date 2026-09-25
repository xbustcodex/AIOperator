"""Runtime bootstrap for Buster OS.

Two-phase lifecycle that preserves the single-runtime invariant:

* **Offline bootstrap** (``bootstrap_offline``) - installation and
  initialization only. Materializes the directory layout, writes default
  config (incl. default grants and protected-path defaults) and records a
  first-run marker. **Never constructs a Kernel.**
* **Runtime seed** (``seed_runtime``) - invoked once by the runtime daemon
  at ``start`` to plant first-run memory/world-model facts into the single
  kernel instance.

Both phases are idempotent: re-running bootstrap is a no-op and never
creates competing runtimes.
"""

import logging
import os
from typing import Optional

from buster.install import resolve_install_path
from buster.version import get_version

SUBDIRS = [
    "config",
    "cache",
    "logs",
    "state",
    "memory",
    "models",
    "agents",
    "packages",
    "workspaces",
    "backups",
]

MARKER_NAME = "bootstrapped"


def bootstrap_offline(config, install_path: Optional[str] = None) -> dict:
    """Installation/initialization phase. No kernel is created."""
    install_path = resolve_install_path(
        explicit=install_path or config.get("install_path"))
    if config.get("install_path") != install_path:
        config.install_path = install_path
        config.save()
    logger = logging.getLogger("buster.bootstrap")

    summary = {
        "version": get_version(),
        "install_path": install_path,
        "first_run": False,
        "layout_created": [],
    }

    # 1. directory layout
    for subdir in SUBDIRS:
        path = os.path.join(install_path, subdir)
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            summary["layout_created"].append(subdir)

    # 2. default configuration (only ever written when absent)
    if not os.path.isfile(config.config_path):
        config.save()
        summary["config_written"] = True

    # 3. first-run marker
    marker = os.path.join(install_path, "state", MARKER_NAME)
    if not os.path.isfile(marker):
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write(get_version() + "\n")
        summary["first_run"] = True

    logger.info("Bootstrap %s for %s", "completed (first run)" if summary["first_run"] else "confirmed",
                install_path)
    return summary


def seed_runtime(kernel) -> dict:
    """Plant first-run seeds into the live kernel (called at start). Idempotent."""
    logger = logging.getLogger("buster.bootstrap")

    # Skip re-seeding when the memory store already carries bootstrap facts.
    if kernel.memory.knowledge.recall("bootstrap.seeded") is True:
        return {"seeded": False}

    facts = {
        "bootstrap.version": get_version(),
        "bootstrap.seeded": True,
        "capabilities": kernel.cap.list_capabilities(),
        "ai_providers": kernel.ai.providers.names(),
    }
    for key, value in facts.items():
        kernel.memory.knowledge.learn(key, value, source="bootstrap", confidence=1.0)
    kernel.memory.experience.record({
        "source": "bootstrap", "target": "start", "status": "done",
        "version": get_version(),
    })
    for key, value in facts.items():
        kernel.world_model.set_fact(key, value)
    kernel.world_model.component_status("bootstrap", "seeded")
    logger.info("Runtime seeds planted.")
    return {"seeded": True}


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")