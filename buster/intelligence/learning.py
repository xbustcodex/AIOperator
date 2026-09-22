"""Learning substrate for Buster OS.

Captures context → intention → plan → action → result → evaluation → lesson
cycles and learns from outcomes. Learning NEVER grants authority: it only
writes to memory (experiences, knowledge lessons, procedural reliability).
Permission changes remain exclusively user/policy-driven.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from buster.capabilities.base import CapabilityResult


@dataclass
class LearningCycle:
    context: str
    intention: str
    plan: str = ""
    action: str = ""
    result_ok: bool = False
    evaluation: str = ""
    lesson: Optional[str] = None
    ts: float = 0.0

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["ts"] = self.ts or time.time()
        return d


class LearningEngine:
    """Distils outcome cycles into experiences, lessons and reliability."""

    def __init__(self, kernel, memory_dir: str):
        self.kernel = kernel
        self.memory_dir = memory_dir
        self.logger = logging.getLogger("buster.intel.learning")

    # -- outcome evaluation ----------------------------------------------

    @staticmethod
    def evaluate(result: CapabilityResult) -> str:
        if result.success:
            return "success"
        lower = (result.error or "").lower()
        if "permission denied" in lower or "denied by default" in lower:
            return "blocked"
        return "failure"

    # -- cycle recording ---------------------------------------------------

    def record_cycle(self, *, context: str, intention: str, plan: str = "",
                     action: str = "", result: Any = None,
                     evaluation: str = "", lesson: Optional[str] = None) -> LearningCycle:
        """Record a context→…→lesson learning cycle."""
        result_ok = bool(result and getattr(result, "success", True))
        cycle = LearningCycle(
            context=context, intention=intention, plan=plan, action=action,
            result_ok=result_ok, evaluation=evaluation or self.evaluate(result)
            if result is not None else "",
            lesson=lesson, ts=time.time(),
        )
        if self.kernel is not None and getattr(self.kernel, "memory", None) is not None:
            self.kernel.memory.experience.record({
                "target": intention,
                "status": "done" if result_ok else "failed",
                "action": action,
                "evaluation": cycle.evaluation,
                "lesson": lesson,
                "learning": True,
            })
        if lesson:
            self._store_lesson(intention, lesson, cycle.evaluation)
        return cycle

    def _store_lesson(self, key_base: str, lesson: str, evaluation: str) -> None:
        knowledge = getattr(getattr(self.kernel, "memory", None), "knowledge", None)
        if knowledge is None:
            return
        confidence = 0.8 if evaluation == "success" else 0.6
        knowledge.learn(f"lesson:{key_base[:60]}", lesson,
                        source="learning", confidence=confidence)

    # -- capability reliability ---------------------------------------------

    def record_capability_outcome(self, action: str, result: CapabilityResult) -> None:
        """Track capability reliability for informed planning."""
        knowledge = getattr(getattr(self.kernel, "memory", None), "knowledge", None)
        if knowledge is None:
            return
        previous = knowledge.recall(f"capability_outcome:{action}", None)
        if previous is None:
            previous = {"uses": 0, "successes": 0, "failures": 0}
        uses = int(previous.get("uses", 0)) + 1
        successes = int(previous.get("successes", 0)) + (1 if result.success else 0)
        failures = int(previous.get("failures", 0)) + (0 if result.success else 1)
        knowledge.learn(
            f"capability_outcome:{action}",
            {"uses": uses, "successes": successes, "failures": failures,
             "reliability": round(successes / uses, 3)},
            source="learning", confidence=0.9,
        )

    # -- procedural learning -------------------------------------------------

    def learn_procedure(self, name: str, steps: list[str]) -> None:
        coordinator = getattr(getattr(self.kernel, "intel", None), "memory", None)
        if coordinator is not None:
            coordinator.procedural.learn_recipe(name, steps)

    def note_procedure_use(self, name: str, success: bool) -> None:
        coordinator = getattr(getattr(self.kernel, "intel", None), "memory", None)
        if coordinator is not None:
            coordinator.procedural.record_use(name, success)