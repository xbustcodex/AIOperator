"""Basal nervous system for Buster OS.

Continuously maintains low-level awareness of the running node WITHOUT
requiring an LLM: samples perception + kernel state, converts raw
observations into a concise set of internal *signals*, tracks node health and
idle/activity state, and surfaces meaningful changes through the event bus.

Deterministic and lightweight by design.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

LEVEL_WEIGHT = {"debug": 0, "ok": 1, "info": 2, "warning": 3, "critical": 4}

BOOTED_AT = 0.0
HEARTBEAT_EVENT = "intel.heartbeat"
SIGNAL_EVENT = "intel.signal"


@dataclass
class Signal:
    kind: str
    level: str
    message: str
    ts: float = field(default_factory=time.time)
    details: dict = field(default_factory=dict)

    @property
    def urgency(self) -> int:
        return LEVEL_WEIGHT.get(self.level, 0)

    def key(self) -> tuple:
        return (self.kind, self.level)


@dataclass
class HealthState:
    overall: str = "healthy"          # healthy | attention | constrained | critical
    warnings: int = 0
    critical: int = 0
    detail: str = ""


class NervousSystem:
    """Base awareness: sensors + kernel state -> normalized signals."""

    def __init__(self, kernel, idle_after: float = 300.0,
                 sleep_after: float = 1800.0):
        self.kernel = kernel
        self.idle_after = idle_after
        self.sleep_after = sleep_after
        self._last_seen: dict[str, tuple] = {}
        self._latest: dict[str, Signal] = {}
        self._last_activity = time.time()
        self._last_connectivity = "unknown"
        self._last_battery_pct: Optional[float] = None
        self.logger = logging.getLogger("buster.intel.nervous")

    # -- activity -----------------------------------------------------

    def touch(self) -> None:
        """Mark node as actively used (user interaction or agent action)."""
        self._last_activity = time.time()

    def activity_state(self) -> str:
        elapsed = time.time() - self._last_activity
        if elapsed < self.idle_after:
            return "active"
        if elapsed < self.sleep_after:
            return "idle"
        return "sleep"

    # -- sampling -----------------------------------------------------

    def snapshot(self) -> dict:
        """Collect a raw observation snapshot of the node."""
        perception = {}
        try:
            perception = self.kernel.perception.snapshot()
        except Exception:  # noqa: BLE001
            self.logger.exception("Perception snapshot failed")
        status = {}
        try:
            status = self.kernel.status()
        except Exception:  # noqa: BLE001
            pass
        memory = {}
        try:
            memory = self.kernel.memory.snapshot()
        except Exception:  # noqa: BLE001
            pass
        return {
            "ts": time.time(),
            "perception": perception,
            "kernel": status,
            "memory": memory,
        }

    # -- evaluation ----------------------------------------------------

    def evaluate(self, snapshot: dict) -> list[Signal]:
        """Convert raw observations into normalized signals."""
        signals: list[Signal] = []
        perception = snapshot.get("perception", {})
        battery = perception.get("battery", {})
        resources = perception.get("resources", {})
        network = perception.get("network", {})
        environment = perception.get("environment", {})
        device = perception.get("device", {})
        kernel_status = snapshot.get("kernel", {})
        memory = snapshot.get("memory", {})
        now = time.time()

        # battery
        pct = battery.get("percentage")
        if isinstance(pct, (int, float)):
            self._battery_trend(pct, signals)
            level = "critical" if pct < 10 else ("warning" if pct < 20 else "ok")
            if level != "ok" or self._last_battery_pct is None:
                signals.append(Signal("battery", level,
                                      f"battery at {int(pct)}%", details={"pct": pct}))
            self._last_battery_pct = pct

            temp = battery.get("temperature")
            if isinstance(temp, (int, float)) and temp > 45.0:
                signals.append(Signal("thermal", "warning",
                                      f"battery temperature {temp}°C", details={"temp": temp}))

        # storage / resources
        disk = environment.get("disk", {})
        free = disk.get("free_bytes")
        if isinstance(free, (int, float)):
            if free < 256 * 1024 * 1024:
                signals.append(Signal("storage", "critical", "storage critically low"))
            elif free < 1024 * 1024 * 1024:
                signals.append(Signal("storage", "warning", "storage low"))

        load = resources.get("load_1m")
        cpus = resources.get("cpus")
        if isinstance(load, (int, float)) and isinstance(cpus, int) and cpus > 0 and load > cpus * 0.9:
            signals.append(Signal("cpu", "warning",
                                  f"high load {load:.1f} on {cpus} cpu(s)",
                                  details={"load": load, "cpus": cpus}))

        mem = resources.get("mem", {})
        available = _mem_kb(mem.get("MemAvailable"))
        total = _mem_kb(mem.get("MemTotal"))
        if available is not None and total and available < total * 0.1:
            signals.append(Signal("memory", "critical", "low available memory"))

        # connectivity
        ips = network.get("ips") or []
        if ips:
            self._last_connectivity = "online"
        elif self._last_connectivity != "offline":
            signals.append(Signal("network", "info", "no usable network interface detected"))
            self._last_connectivity = "offline"

        # capability health
        expected_core = {"filesystem", "shell", "android", "search"}
        installed = set(kernel_status.get("capabilities", []))
        missing = expected_core - installed
        if missing:
            signals.append(Signal("capability", "warning",
                                  f"core capabilities missing: {sorted(missing)}",
                                  details={"missing": sorted(missing)}))

        # AI providers
        providers = kernel_status.get("ai_providers", [])
        if not providers:
            signals.append(Signal("provider", "warning", "no AI providers registered"))

        # job health
        jobs = kernel_status.get("jobs", [])
        failed_jobs = [j for j in jobs if j.get("status") == "failed"]
        if failed_jobs:
            signals.append(Signal("job", "warning",
                                  f"{len(failed_jobs)} failed job(s)", details={"jobs": failed_jobs}))

        # memory health
        store_keys = memory.get("store_keys", [])
        if len(store_keys) > 2000:
            signals.append(Signal("memory", "info", "memory store is large; consolidation due"))

        # TerminalP host state
        host = device.get("host")
        if host not in ("terminalp", "termux", "android-terminal") and host is not None:
            signals.append(Signal("host", "info",
                                  f"running on non-phone host '{host}'", details={"host": host}))
        return signals

    def _battery_trend(self, pct: float, signals: list[Signal]) -> None:
        if self._last_battery_pct is not None and pct < self._last_battery_pct - 5:
            signals.append(Signal("battery", "info", "battery draining",
                                  details={"delta": self._last_battery_pct - pct}))

    # -- dedup + publish -------------------------------------------------

    def heed(self, snapshot: Optional[dict] = None) -> list[Signal]:
        """Evaluate, deduplicate against previous state, and surface novelty."""
        snapshot = snapshot or self.snapshot()
        fresh = self.evaluate(snapshot)
        surfaced: list[Signal] = []
        for signal in fresh:
            previous = self._last_seen.get(signal.kind)
            changed = previous != (signal.level, signal.message)
            if changed:
                surfaced.append(signal)
                self._last_seen[signal.kind] = (signal.level, signal.message)
            self._latest[signal.kind] = signal
        for signal in surfaced:
            if signal.urgency >= 2:
                self._emit(SIGNAL_EVENT, {"kind": signal.kind,
                                          "level": signal.level,
                                          "message": signal.message})
        self._emit(HEARTBEAT_EVENT, {"ts": time.time(),
                                     "activity": self.activity_state(),
                                     "signals": len(self._latest)})
        return surfaced

    def health(self) -> HealthState:
        """Aggregate current signals into an overall node-health summary."""
        warnings = sum(1 for s in self._latest.values() if s.level == "warning")
        critical = sum(1 for s in self._latest.values() if s.level == "critical")
        if critical:
            return HealthState("critical", warnings, critical, "critical signals present")
        if warnings or self.activity_state() != "sleep":
            if warnings:
                return HealthState("attention", warnings, 0, f"{warnings} warning(s)")
            return HealthState("healthy", 0, 0, "nominal")
        return HealthState("healthy", warnings, 0, "nominal")

    def signals(self) -> list[dict]:
        out = []
        for signal in self._latest.values():
            out.append({"kind": signal.kind, "level": signal.level,
                        "message": signal.message, "ts": signal.ts,
                        "details": signal.details})
        return out

    def state(self, snapshot: Optional[dict] = None) -> dict:
        snapshot = snapshot or self.snapshot()
        health = self.health()
        return {
            "ts": time.time(),
            "activity": self.activity_state(),
            "health": {"overall": health.overall, "warnings": health.warnings,
                       "critical": health.critical, "detail": health.detail},
            "signals": self.signals(),
            "kernel": {k: snapshot["kernel"].get(k) for k in
                       ("state", "event_router_running", "scheduler_running")},
            "host": snapshot["perception"].get("device", {}).get("host"),
        }

    def _emit(self, event_type: str, payload: dict) -> None:
        if self.kernel is not None and getattr(self.kernel, "event_router", None) is not None \
                and self.kernel.event_router.running:
            self.kernel.event_router.emit(event_type, payload)


def _mem_kb(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    try:
        if "kB" in text:
            return float(text.replace("kB", "").strip())
        return float(text.split()[0])
    except ValueError:
        return None