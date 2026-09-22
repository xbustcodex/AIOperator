"""Reflection engine: distill experiences into learned knowledge.

Reflection hooks run at configurable points (after agent runs, periodically)
and apply rule-based distillations into the KnowledgeMemory. Extensible with
custom ``hooks``.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

ReflectionHook = Callable[[dict], Optional[dict]]


@dataclass
class ReflectionEngine:
    """Applies reflection hooks over fresh experiences."""

    knowledge: object = None
    hooks: list[ReflectionHook] = field(default_factory=list)

    def __post_init__(self):
        self.logger = logging.getLogger("buster.memory.reflection")
        if not self.hooks:
            self.hooks = [
                reflect_failures,
                reflect_targets,
                reflect_winning_patterns,
                reflect_agent_usage,
            ]

    def on_experience(self, entry: dict) -> None:
        """Run hooks against a single fresh experience record."""
        if self.knowledge is None:
            return
        for hook in self.hooks:
            try:
                learning = hook(entry)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(learning, dict) and "key" in learning:
                self.knowledge.learn(
                    learning["key"], learning.get("value"),
                    source=learning.get("source", "reflection"),
                    confidence=learning.get("confidence", 0.4),
                )

    def reflect(self, experiences: list[dict]) -> int:
        """Reflect over a batch; returns the number of new learnings."""
        before = len(self.knowledge.keys()) if self.knowledge is not None else 0
        for entry in experiences:
            self.on_experience(entry)
        after = len(self.knowledge.keys()) if self.knowledge is not None else before
        return after - before


def reflect_failures(entry: dict) -> Optional[dict]:
    """Learn from failing runs: avoid repeating the failed goal shape."""
    if entry.get("status") == "failed" and entry.get("target"):
        return {
            "key": f"avoid_repeat:{entry['target'][:60]}",
            "value": entry.get("error", "unknown failure"),
            "source": "reflection:failures",
            "confidence": 0.6,
        }
    return None


def reflect_targets(entry: dict) -> Optional[dict]:
    """Track handled goals to surface recurring work."""
    if entry.get("target"):
        return {
            "key": f"goal_seen:{entry['target'][:60]}",
            "value": entry.get("status", "unknown"),
            "source": "reflection:targets",
            "confidence": 0.3,
        }
    return None


def reflect_winning_patterns(entry: dict) -> Optional[dict]:
    """Remember a documented winning pattern for a successful goal shape."""
    if entry.get("status") == "done" and entry.get("target"):
        return {
            "key": f"pattern:{entry['target'][:60]}",
            "value": "done",
            "source": "reflection:patterns",
            "confidence": 0.6,
        }
    return None


def reflect_agent_usage(entry: dict) -> Optional[dict]:
    """Track which agents complete goals, feeding routing decisions."""
    agent = entry.get("agent")
    if agent and entry.get("status") == "done":
        return {
            "key": f"agent_working:{agent}",
            "value": entry.get("target", "")[:80],
            "source": "reflection:agents",
            "confidence": 0.4,
        }
    return None