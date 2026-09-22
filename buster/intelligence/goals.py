"""Goal / intention system for Buster OS.

A persisted registry of user, system, task and subgoals with priorities,
dependencies, status, progress and provenance.

I am explicitly NOT a scheduler: the Kernel scheduler remains the sole
authority for execution timing. Goals are state. Any scheduled work that
serves a goal is scheduled through ``kernel.scheduler``.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Goal:
    id: str
    title: str
    kind: str = "user"          # user | system | task | subgoal
    status: str = "active"      # active | paused | completed | failed | cancelled
    priority: int = 0           # higher = more important
    progress: float = 0.0       # 0..1
    dependencies: list = field(default_factory=list)
    blocker: Optional[str] = None
    provenance: str = "user"    # who/what created it
    agent: Optional[str] = None
    parent: Optional[str] = None
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {k: (v if not hasattr(v, "isoformat") else v)
                for k, v in self.__dict__.items()}


class GoalStore:
    """Persisted goal registry."""

    def __init__(self, state_dir: str):
        self._path = os.path.join(state_dir, "goals.json")
        self._goals: dict[str, Goal] = {}
        os.makedirs(state_dir, exist_ok=True)
        self._load()

    # -- mutations ----------------------------------------------------

    def create(self, title: str, kind: str = "user", priority: int = 0,
               provenance: str = "user", parent: Optional[str] = None,
               dependencies: Optional[list] = None, agent: Optional[str] = None) -> Goal:
        goal = Goal(
            id=uuid.uuid4().hex[:12],
            title=title, kind=kind, priority=priority,
            provenance=provenance, parent=parent,
            dependencies=list(dependencies or []), agent=agent,
        )
        existing = [g for g in self._goals.values() if g.title == title and g.status == "active"]
        if existing:
            return existing[0]  # deduplicate active goals with identical titles
        self._goals[goal.id] = goal
        self._save()
        return goal

    def get(self, goal_id: str) -> Optional[Goal]:
        return self._goals.get(goal_id)

    def update(self, goal_id: str, **fields) -> Optional[Goal]:
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        for key, value in fields.items():
            if hasattr(goal, key):
                setattr(goal, key, value)
        goal.updated = time.time()
        self._save()
        return goal

    def complete(self, goal_id: str) -> None:
        self.update(goal_id, status="completed", progress=1.0)

    def fail(self, goal_id: str, blocker: Optional[str] = None) -> None:
        self.update(goal_id, status="failed", blocker=blocker)
        self._notify("goal.failed", goal_id)

    def cancel(self, goal_id: str) -> None:
        self.update(goal_id, status="cancelled")

    def spawn_subgoal(self, parent_id: str, title: str, priority: int = 0) -> Goal:
        return self.create(title, kind="subgoal", priority=priority,
                           parent=parent_id, provenance="derived")

    def active(self) -> list[Goal]:
        return self.list_goals(status="active")

    def list_goals(self, status: Optional[str] = None) -> list[Goal]:
        goals = list(self._goals.values())
        if status:
            goals = [g for g in goals if g.status == status]
        goals.sort(key=lambda g: g.priority, reverse=True)
        return goals

    def close_stale(self, horizon: float = 7 * 86400) -> int:
        """Mark ancient still-active goals as failed so they don't leak."""
        now = time.time()
        closed = 0
        for goal in self.active():
            if now - goal.updated > horizon:
                goal.status = "failed"
                goal.blocker = "stale"
                goal.updated = now
                closed += 1
        if closed:
            self._save()
        return closed

    # -- diagnostics ----------------------------------------------------

    def stats(self) -> dict:
        counts = {}
        for goal in self._goals.values():
            counts[goal.status] = counts.get(goal.status, 0) + 1
        return {"total": len(self._goals), "by_status": counts}

    def _notify(self, event_type: str, goal_id: str) -> None:
        # goal events are surfaced by generators; state is the source of truth
        pass

    # -- persistence ------------------------------------------------------

    def _load(self) -> None:
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                rows = json.load(handle)
            for row in rows:
                self._goals[row["id"]] = Goal(**{k: row.get(k) for k in
                                                 Goal.__dataclass_fields__})
        except (ValueError, OSError, TypeError):
            self._goals = {}

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump([g.as_dict() for g in self._goals.values()], handle, indent=2)