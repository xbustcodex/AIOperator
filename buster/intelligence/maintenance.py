"""Self-observation and bounded maintenance for Buster OS.

Inspects runtime, configuration, memory, capability, provider, scheduler,
RPC, audit and TerminalP integration health, and provides bounded,
non-destructive recovery (e.g. memory pruning). It never performs
self-modifying code or bypasses policy.
"""

import logging
import os

from buster.android_integration.device import host_identity, is_termux_compatible


class SelfMaintenance:
    """Diagnostics + bounded recovery."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.logger = logging.getLogger("buster.intel.maintenance")

    def diagnostics(self) -> dict:
        report = {}

        report["runtime"] = {
            "state": self.kernel.state,
            "event_router": self.kernel.event_router.running,
            "scheduler": self.kernel.scheduler.running,
        }
        report["config"] = {
            "path": self.kernel.config.config_path,
            "readable": os.path.isfile(self.kernel.config.config_path),
        }
        report["memory"] = self.kernel.intel.memory.stats()
        report["capabilities"] = {"registered": self.kernel.cap.list_capabilities(),
                                  "actions": len(self.kernel.cap.list_actions())}
        report["providers"] = self.kernel.intel.providers.health()
        report["scheduler"] = {
            "jobs": [{"name": j.name, "status": j.status.value}
                     for j in self.kernel.scheduler.list_jobs()],
        }
        report["rpc"] = {"lock_online": self._rpc_online()}
        report["audit"] = self._audit_health()
        report["terminalp"] = {
            "host": host_identity(),
            "compatible": is_termux_compatible(),
        }

        report["overall"] = "healthy"
        problems = []
        if not report["runtime"]["scheduler"]:
            report["overall"] = "degraded"
            problems.append("scheduler down")
        if not report["providers"]["local_available"]:
            report["overall"] = "degraded"
            problems.append("no local AI provider")
        if not report["config"]["readable"]:
            problems.append("config unreadable")
        if problems:
            report["overall"] = "attention"
            report["notes"] = problems
        return report

    def _rpc_online(self) -> bool:
        from buster.runtime import RuntimeLock
        install = self.kernel.config.install_path
        return RuntimeLock(install).is_online()

    def _audit_health(self) -> dict:
        path = os.path.join(self.kernel.config.install_path, "logs", "audit.jsonl")
        ok = os.path.isfile(path)
        size = os.path.getsize(path) if ok else 0
        return {"present": ok, "bytes": size, "ok": ok}

    def recover(self, component: str = "memory") -> dict:
        """Bounded, non-destructive recovery."""
        if component == "memory":
            report = self.kernel.intel.memory.consolidate()
            return {"component": "memory", "action": "consolidate", "report": report}
        if component == "provider":
            # re-register the local provider if missing
            if "local" not in self.kernel.ai.providers.names():
                from buster.ai_providers.local import LocalProvider
                self.kernel.ai.providers.register(LocalProvider(), default=True)
            return {"component": "provider", "action": "ensure_local", "ok": True}
        return {"component": component, "action": "unsupported"}

    def state(self) -> dict:
        return self.diagnostics()