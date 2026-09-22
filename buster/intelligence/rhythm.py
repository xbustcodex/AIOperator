"""Cognitive rhythm for Buster OS.

A deterministic state machine that classifies the node's current cognitive
mode from nervous-system signals, activity, goals and time. It gates
expensive cognition (reflection, consolidation, proactive analysis) so Buster
only does heavy work when it is useful.
"""

import logging
import time
from enum import Enum
from typing import Optional


class Rhythm(Enum):
    ACTIVE = "active"            # user / high-priority interaction
    BACKGROUND = "background"    # background jobs running
    IDLE = "idle"
    REFLECTION = "reflection"    # reflection opportunity is open
    MAINTENANCE = "maintenance"  # maintenance opportunity is open
    CONSTRAINED = "constrained"  # resource pressure
    DEGRADED = "degraded"        # connectivity / provider degraded
    RECOVERY = "recovery"        # just recovered from a problem
    SLEEP = "sleep"              # low-activity, conserve


class CognitiveRhythm:
    """Tracks and transitions the node's cognitive mode."""

    def __init__(self, kernel, idle_time: float = 300.0,
                 maintenance_interval: float = 3600.0,
                 reflection_interval: float = 1800.0):
        self.kernel = kernel
        self.idle_time = idle_time
        self.maintenance_interval = maintenance_interval
        self.reflection_interval = reflection_interval
        self.current = Rhythm.IDLE
        self._last_maintenance = time.time()
        self._last_reflection = time.time()
        self._last_recovery = 0.0
        self.logger = logging.getLogger("buster.intel.rhythm")

    # -- transitions ----------------------------------------------------

    def transition(self, nervous_state: dict, pending_goals: int = 0,
                   active_jobs: int = 0) -> Rhythm:
        activity = nervous_state.get("activity", "idle")
        health = nervous_state.get("health", {})
        overall = health.get("overall", "healthy")
        now = time.time()

        if overall == "critical":
            target = Rhythm.CONSTRAINED
        elif overall == "attention":
            target = Rhythm.DEGRADED
        elif activity == "active" or pending_goals > 0:
            target = Rhythm.ACTIVE
        elif active_jobs > 0:
            target = Rhythm.BACKGROUND
        elif activity == "sleep":
            target = Rhythm.SLEEP
        elif self._maintenance_due(now):
            target = Rhythm.MAINTENANCE
        elif self._reflection_due(now):
            target = Rhythm.REFLECTION
        else:
            target = Rhythm.IDLE

        if target == Rhythm.ACTIVE or target == Rhythm.BACKGROUND:
            self._last_maintenance = now
            self._last_reflection = now

        if target != Rhythm.CONSTRAINED and self.current == Rhythm.CONSTRAINED:
            # emerged from resource pressure
            target = Rhythm.RECOVERY
            if now - self._last_recovery < 60:
                target = Rhythm.IDLE
            self._last_recovery = now

        if target != self.current:
            self.logger.info("Rhythm: %s -> %s", self.current.value, target.value)
            self._emit(target)
        self.current = target
        return target

    # -- guards -----------------------------------------------------------

    def should_reflect(self) -> bool:
        return self.current in (Rhythm.REFLECTION, Rhythm.IDLE, Rhythm.ACTIVE)

    def should_consolidate(self) -> bool:
        return self.current in (Rhythm.MAINTENANCE, Rhythm.RECOVERY, Rhythm.IDLE)

    def should_maintain(self) -> bool:
        return self.current == Rhythm.MAINTENANCE

    def _maintenance_due(self, now: float) -> bool:
        return now - self._last_maintenance >= self.maintenance_interval

    def _reflection_due(self, now: float) -> bool:
        return now - self._last_reflection >= self.reflection_interval

    # -- introspection ----------------------------------------------------

    def state(self) -> dict:
        return {
            "state": self.current.value,
            "last_maintenance": self._last_maintenance,
            "last_reflection": self._last_reflection,
        }

    def _emit(self, rhythm: Rhythm) -> None:
        if self.kernel is not None and getattr(self.kernel, "event_router", None) is not None \
                and self.kernel.event_router.running:
            self.kernel.event_router.emit("rhythm.state",
                                          {"state": rhythm.value})