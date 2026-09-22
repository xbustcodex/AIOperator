"""Proactive intelligence for Buster OS.

Recognizes meaningful patterns (recurring failure, resource problems, broken
capabilities, stalled jobs, unfinished goals, maintenance opportunities,
learned patterns) and converts them into structured *suggestions*.

Suggestions are observations, not actions: they never execute anything and
never bypass authority. Policy decides whether a suggestion may become a
goal or permitted action.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Suggestion:
    id: str
    kind: str
    summary: str
    evidence: dict = field(default_factory=dict)
    confidence: float = 0.5
    ts: float = field(default_factory=time.time)


class ProactiveEngine:
    """Detects patterns and persists structured suggestions."""

    def __init__(self, kernel, state_dir: str):
        self.kernel = kernel
        self._path = os.path.join(state_dir, "suggestions.json")
        self._suggestions: list[Suggestion] = []
        os.makedirs(state_dir, exist_ok=True)
        self._load()

    # -- detection ----------------------------------------------------------

    def tick(self) -> list[Suggestion]:
        fresh: list[Suggestion] = []

        # recurring failure
        from buster.intelligence.curiosity import CuriosityEngine
        for question in CuriosityEngine(self.kernel).questions(limit=4):
            if question["kind"] == "repeated_problem":
                fresh.append(Suggestion(
                    id=uuid.uuid4().hex[:12], kind="recurring_failure",
                    summary=question["question"], evidence=question["evidence"],
                    confidence=0.6))

        # resource problem from nervous signals
        for signal in self.kernel.intel.nervous.signals():
            if signal["kind"] in ("storage", "memory", "cpu", "thermal") and \
                    signal["level"] in ("warning", "critical"):
                fresh.append(Suggestion(
                    id=uuid.uuid4().hex[:12], kind="resource_problem",
                    summary=signal["message"], evidence={"kind": signal["kind"]},
                    confidence=0.7))

        # unfinished goals
        for goal in self.kernel.intel.goals.active():
            age = time.time() - goal.updated
            if age > 3600:
                fresh.append(Suggestion(
                    id=uuid.uuid4().hex[:12], kind="unfinished_goal",
                    summary=f"goal '{goal.title[:60]}' has been active for {int(age // 60)}m",
                    evidence={"goal_id": goal.id}, confidence=0.5))

        # maintenance opportunity
        stats = self.kernel.intel.memory.stats()
        if stats["experience_count"] > 200:
            fresh.append(Suggestion(
                id=uuid.uuid4().hex[:12], kind="maintenance_opportunity",
                summary="experience store is large; consolidation recommended",
                evidence={"experience_count": stats["experience_count"]}))
        if len(self.kernel.memory.store.keys()) > 500:
            fresh.append(Suggestion(
                id=uuid.uuid4().hex[:12], kind="maintenance_opportunity",
                summary="key/value store is large; TTL pruning recommended",
                evidence={"store_keys": len(self.kernel.memory.store.keys())}))

        # provider healthy again (recovery signal)
        provider_health = self.kernel.intel.providers.health()
        if provider_health["remote_configured"] and provider_health["remote_available"]:
            fresh.append(Suggestion(
                id=uuid.uuid4().hex[:12], kind="connectivity_recovered",
                summary="remote AI provider is reachable again",
                evidence={}, confidence=0.3))

        self._merge(fresh)
        return fresh

    # -- access ------------------------------------------------------------

    def suggestions(self, limit: int = 20) -> list[dict]:
        recent = sorted(self._suggestions, key=lambda s: s.ts, reverse=True)
        return [{"id": s.id, "kind": s.kind, "summary": s.summary,
                 "evidence": s.evidence, "confidence": s.confidence, "ts": s.ts}
                for s in recent[:limit]]

    def clear(self) -> None:
        self._suggestions.clear()
        self._save()

    # -- persistence ----------------------------------------------------------

    def _merge(self, fresh: list[Suggestion]) -> None:
        seen = {s.summary for s in self._suggestions[-20:]}
        for suggestion in fresh:
            if suggestion.summary not in seen:
                self._suggestions.append(suggestion)
                seen.add(suggestion.summary)
        self._suggestions = self._suggestions[-50:]
        self._save()

    def _load(self) -> None:
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                rows = json.load(handle)
            for row in rows:
                self._suggestions.append(Suggestion(
                    id=row["id"], kind=row["kind"], summary=row["summary"],
                    evidence=row.get("evidence", {}),
                    confidence=row.get("confidence", 0.5), ts=row.get("ts", time.time())))
        except (ValueError, OSError, TypeError):
            self._suggestions = []

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump([{"id": s.id, "kind": s.kind, "summary": s.summary,
                        "evidence": s.evidence, "confidence": s.confidence, "ts": s.ts}
                       for s in self._suggestions], handle, indent=2)