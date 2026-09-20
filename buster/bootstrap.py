"""Runtime bootstrap for Buster OS.

Materializes the environment on first run: creates the install layout,
applies default permission grants, seeds initial memory and world-model
facts, and records that bootstrapping completed. Idempotent and safe to
re-run; the ``--check`` / doctor flow can reuse it.
"""

import logging
import os
from typing import Optional

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


class BootstrapManager:
    """First-run bootstrap materializer bound to a running Kernel."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.logger = logging.getLogger("buster.bootstrap")

    # -- public routine -------------------------------------------------

    def run(self, apply_grants: bool = True, seed_memory: bool = True) -> dict:
        """Execute the full bootstrap. Returns a summary dict."""
        install_path = self._install_path()
        summary = {
            "version": get_version(),
            "install_path": install_path,
            "layout": self.ensure_layout(),
            "grants_applied": [],
        }

        if apply_grants:
            summary["grants_applied"] = self.ensure_default_grants()

        first_run = self._is_first_run()
        summary["first_run"] = first_run

        if seed_memory and first_run:
            summary["seed"] = self.seed_memory()

        summary["facts"] = self.seed_world_model()

        if first_run:
            self._mark_bootstrapped()
            self.logger.info("Buster environment bootstrapped v%s", get_version())
        else:
            self.logger.info("Buster environment already bootstrapped")

        return summary

    # -- layout ----------------------------------------------------------

    def ensure_layout(self) -> list[str]:
        base = self._install_path()
        created = []
        for subdir in SUBDIRS:
            path = os.path.join(base, subdir)
            if not os.path.isdir(path):
                os.makedirs(path, exist_ok=True)
                created.append(path)
        return created

    # -- permission seeds -------------------------------------------------

    def ensure_default_grants(self) -> list[str]:
        """Grant actions listed in ``security.default_grants`` config.

        May be a list of strings, or a dict mapping action -> note.
        Existing rules are left untouched (grants accumulate).
        """
        grants = self.kernel.config.get_nested("security.default_grants", []) or []
        if isinstance(grants, dict):
            grants = list(grants.keys())
        applied = []
        existing = [rule["action"] for rule in self.kernel.permissions.to_rules()]
        for action in grants:
            if action in existing:
                continue
            self.kernel.permissions.grant(action, note="bootstrap default grant")
            applied.append(action)
        return applied

    # -- memory seeds ------------------------------------------------------

    def seed_memory(self) -> dict:
        """Write first-run markers into experience and knowledge stores."""
        try:
            self.kernel.memory.experience.record({
                "source": "bootstrap",
                "target": "bootstrap",
                "status": "done",
                "version": get_version(),
            })
        except Exception:  # noqa: BLE001
            self.logger.exception("Bootstrap experience seed failed")
        try:
            self.kernel.memory.knowledge.learn(
                "bootstrap.version", get_version(),
                source="bootstrap", confidence=1.0,
            )
            self.kernel.memory.knowledge.learn(
                "bootstrap.first_run_at", _now_iso(),
                source="bootstrap", confidence=1.0,
            )
        except Exception:  # noqa: BLE001
            self.logger.exception("Bootstrap knowledge seed failed")
        return {
            "experience": self.kernel.memory.experience.count(),
            "knowledge": self.kernel.memory.knowledge.keys(),
        }

    # -- world model seeds --------------------------------------------------

    def seed_world_model(self) -> dict:
        """Record environment facts into the world model."""
        facts = {
            "install_path": self._install_path(),
            "ai_providers": self.kernel.ai.providers.names(),
            "capabilities": self.kernel.cap.list_capabilities(),
        }
        for key, value in facts.items():
            self.kernel.world_model.set_fact(key, value)
        return facts

    # -- helpers -----------------------------------------------------------

    def _install_path(self) -> str:
        return self.kernel.config.get("install_path", os.path.expanduser("~/.buster/"))

    def _state_dir(self) -> str:
        return os.path.join(self._install_path(), "state")

    def _marker_path(self) -> str:
        return os.path.join(self._state_dir(), MARKER_NAME)

    def _is_first_run(self) -> bool:
        return not os.path.isfile(self._marker_path())

    def _mark_bootstrapped(self) -> None:
        os.makedirs(self._state_dir(), exist_ok=True)
        with open(self._marker_path(), "w", encoding="utf-8") as handle:
            handle.write(get_version() + "\n")


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")