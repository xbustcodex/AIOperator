"""Bounded curiosity for Buster OS.

Detects meaningful knowledge gaps (repeated problems, stale goals, unused
capabilities, degraded providers) and converts them into explicit, prioritized
questions and hypotheses. Curiosity never performs autonomous investigation;
any external action to follow up must go through normal capabilities and
permissions.
"""

import logging
import time
from typing import Optional


class CuriosityEngine:
    """Produces prioritized gap questions; suppresses trivial noise."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.logger = logging.getLogger("buster.intel.curiosity")

    # -- gap detection --------------------------------------------------------

    def questions(self, limit: int = 8) -> list[dict]:
        questions: list[dict] = []

        # repeated failed goals without an established lesson
        experiences = self.kernel.memory.experience.recall(limit=40)
        failure_counts: dict[str, int] = {}
        for entry in experiences:
            if entry.get("status") == "failed":
                target = entry.get("target", "")[:60]
                if target:
                    failure_counts[target] = failure_counts.get(target, 0) + 1
        for target, count in failure_counts.items():
            if count >= 2 and not self._has_lesson(target):
                questions.append({
                    "rank": 1.0, "kind": "repeated_problem",
                    "question": f"What reliably solves '{target}'?",
                    "evidence": {"target": target, "failures": count},
                })

        # stalled / stale active goals
        for goal in self.kernel.intel.goals.active():
            age = time.time() - goal.updated
            if age > 3600 and goal.progress == 0.0:
                questions.append({
                    "rank": 0.7, "kind": "stalled_goal",
                    "question": f"Why has goal '{goal.title[:60]}' made no progress?",
                    "evidence": {"goal_id": goal.id, "age_seconds": int(age)},
                })

        # previously unknown provider capability
        provider_health = self.kernel.intel.providers.health()
        if provider_health.get("remote_configured") and not provider_health.get("remote_available"):
            questions.append({
                "rank": 0.6, "kind": "provider",
                "question": "Is the remote AI provider reachable again?",
                "evidence": {"provider": "remote"},
            })

        # never-used capabilities in the registry
        used = {entry.get("action", "") for entry in experiences}
        for action in self.kernel.cap.list_actions():
            if action.startswith("android.") and action not in used:
                questions.append({
                    "rank": 0.2, "kind": "untested_capability",
                    "question": f"What does '{action}' return on this TerminalP host?",
                    "evidence": {"action": action},
                })

        questions.sort(key=lambda q: q["rank"], reverse=True)
        return questions[:limit]

    # -- helpers ---------------------------------------------------------------

    def _has_lesson(self, target: str) -> bool:
        knowledge = getattr(self.kernel.memory, "knowledge", None)
        if knowledge is None:
            return False
        return bool(knowledge.recall(f"lesson:{target[:50]}", None)) or \
            bool(knowledge.search(f"lesson:{target[:20]}", limit=1))

    def state(self) -> dict:
        return {"questions": self.questions(limit=8)}