"""Bounded reflection for Buster OS.

Complements the existing (event-driven) ReflectionEngine with explicit,
rivm-gated reflection passes that turn experience into lessons, hypotheses,
and unresolved questions. Reflection never runs uninterrupted loops, never by
passes permissions, and never mutates protected system components.
"""

import logging
import time
from typing import Optional

LESSON_PATTERNS = 3  # how many "-? ?" occurs before a reflection on failure


class ReflectionCoordinator:
    """Rich reflection on top of the existing ReflectionEngine."""

    def __init__(self, kernel, engine=None):
        self.kernel = kernel
        self.engine = engine or getattr(getattr(kernel, "memory", None), "reflection", None)
        self._last_reflection = 0.0
        self.logger = logging.getLogger("buster.intel.reflection")

    # -- triggers ------------------------------------------------------------

    def trigger_after_goal(self, goal_id: str, outcome: str) -> None:
        self.reflect_now(reason=f"goal {outcome}:{goal_id}")

    def should_reflect(self, rhythm_state: str,
                       recent_failures: int = 0) -> bool:
        now = time.time()
        if now - self._last_reflection < 300:
            return False
        return rhythm_state in ("idle", "reflection", "recovery", "maintenance") or \
            recent_failures >= 2

    # -- pass ----------------------------------------------------------------

    def reflect_now(self, reason: str = "scheduled",
                    max_outputs: int = 8) -> list[dict]:
        """Run one bounded reflection pass; returns produced items."""
        self._last_reflection = time.time()
        outputs: list[dict] = []
        if self.engine is not None and self.kernel is not None:
            experiences = self.kernel.memory.experience.recall(limit=30)
            self.engine.reflect(experiences)
            outputs += self._lessons_from_experiences(experiences)
            outputs += self._hypotheses_from_failures(experiences)
            outputs += self._unresolved_questions(experiences)
        outputs = outputs[:max_outputs]
        self.logger.info("Reflection pass (%s) produced %d item(s)", reason, len(outputs))
        return outputs

    # -- production ------------------------------------------------------------

    def _lessons_from_experiences(self, experiences: list[dict]) -> list[dict]:
        knowledge = getattr(getattr(self.kernel, "memory", None), "knowledge", None)
        if knowledge is None:
            return []
        outputs = []
        for entry in experiences[-12:]:
            if entry.get("status") == "done" and entry.get("lesson"):
                key = f"reflected_lesson:{entry.get('target', '')[:50]}"
                knowledge.learn(key, entry["lesson"], source="reflection", confidence=0.7)
                outputs.append({"kind": "lesson", "key": key, "value": entry["lesson"]})
        return outputs

    def _hypotheses_from_failures(self, experiences: list[dict]) -> list[dict]:
        knowledge = getattr(getattr(self.kernel, "memory", None), "knowledge", None)
        if knowledge is None:
            return []
        outputs = []
        counts: dict[str, list] = {}
        for entry in experiences:
            target = entry.get("target", "")
            if entry.get("status") == "failed" and target:
                counts.setdefault(target, []).append(entry.get("error", ""))
        for target, errors in counts.items():
            if len(errors) >= 2:
                hypothesis = f"repeated failure on '{target[:60]}' suggests {errors[0][:80]}"
                key = f"hypothesis:{target[:50]}"
                knowledge.learn(key, hypothesis, source="reflection", confidence=0.5)
                outputs.append({"kind": "hypothesis", "key": key, "value": hypothesis})
        return outputs

    def _unresolved_questions(self, experiences: list[dict]) -> list[dict]:
        knowledge = getattr(getattr(self.kernel, "memory", None), "knowledge", None)
        if knowledge is None:
            return []
        outputs = []
        # recurring failures with no established lesson become open questions
        for entry in experiences[-10:]:
            if entry.get("status") == "failed" and not entry.get("lesson"):
                question = f"What reliably resolves '{entry.get('target', '')[:60]}'?"
                key = f"question:{entry.get('target', '')[:50]}"
                if not knowledge.recall(key, None):
                    knowledge.learn(key, question, source="reflection", confidence=0.4)
                    outputs.append({"kind": "question", "key": key, "value": question})
        return outputs

    def stats(self) -> dict:
        knowledge = getattr(getattr(self.kernel, "memory", None), "knowledge", None)
        if knowledge is None:
            return {"lessons": 0, "hypotheses": 0, "questions": 0}
        return {
            "lessons": len(knowledge.search("lesson:")),
            "reflected_lessons": len(knowledge.search("reflected_lesson:")),
            "hypotheses": len(knowledge.search("hypothesis:")),
            "questions": len(knowledge.search("question:")),
            "last_reflection": self._last_reflection,
        }