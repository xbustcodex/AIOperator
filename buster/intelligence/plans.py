"""Structured plans and replanning for Buster OS.

Plans express *intent* — a structured, ordered list of capability steps with
reasons — separate from execution. Execution remains capability-based through
the kernel; plans are persisted so reasoning survives restarts and supports
replanning after failures.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlanStep:
    action: str
    params: dict = field(default_factory=dict)
    reason: str = ""
    status: str = "pending"     # pending | running | succeeded | failed | skipped
    observation: str = ""

    def as_dict(self) -> dict:
        return self.__dict__


@dataclass
class Plan:
    id: str
    goal_id: str
    title: str
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "active"      # active | completed | failed | cancelled
    provider: Optional[str] = None
    replanned: int = 0
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "goal_id": self.goal_id, "title": self.title,
            "steps": [s.as_dict() for s in self.steps],
            "status": self.status, "provider": self.provider,
            "replanned": self.replanned, "created": self.created,
            "updated": self.updated,
        }


class PlanStore:
    """Persisted plan registry."""

    def __init__(self, state_dir: str):
        self._path = os.path.join(state_dir, "plans.json")
        self._plans: dict[str, Plan] = {}
        os.makedirs(state_dir, exist_ok=True)
        self._load()

    def create(self, goal_id: str, title: str,
               steps: Optional[list[PlanStep]] = None,
               provider: Optional[str] = None) -> Plan:
        plan = Plan(id=uuid.uuid4().hex[:12], goal_id=goal_id, title=title,
                    steps=steps or [], provider=provider)
        self._plans[plan.id] = plan
        self._save()
        return plan

    def get(self, plan_id: str) -> Optional[Plan]:
        return self._plans.get(plan_id)

    def for_goal(self, goal_id: str) -> list[Plan]:
        return [p for p in self._plans.values() if p.goal_id == goal_id]

    def update_step(self, plan_id: str, index: int, status: str,
                    observation: str = "") -> Optional[Plan]:
        plan = self._plans.get(plan_id)
        if plan is None or index >= len(plan.steps):
            return None
        plan.steps[index].status = status
        plan.steps[index].observation = observation[:500]
        plan.updated = time.time()
        self._save()
        return plan

    def set_steps(self, plan_id: str, steps: list[PlanStep]) -> Optional[Plan]:
        """Replace the plan's steps with materialized execution results."""
        plan = self._plans.get(plan_id)
        if plan is None:
            return None
        plan.steps = list(steps)
        plan.updated = time.time()
        self._save()
        return plan

    def finish(self, plan_id: str, status: str) -> None:
        plan = self._plans.get(plan_id)
        if plan:
            plan.status = status
            plan.updated = time.time()
            self._save()

    def append_steps(self, plan_id: str, steps: list[PlanStep]) -> None:
        plan = self._plans.get(plan_id)
        if plan:
            plan.steps.extend(steps)
            plan.replanned += 1
            plan.status = "active"
            plan.updated = time.time()
            self._save()

    def purge_goal(self, goal_id: str) -> int:
        removed = [pid for pid, p in self._plans.items() if p.goal_id == goal_id]
        for pid in removed:
            del self._plans[pid]
        if removed:
            self._save()
        return len(removed)

    def list_plans(self, status: Optional[str] = None) -> list[Plan]:
        plans = list(self._plans.values())
        if status:
            plans = [p for p in plans if p.status == status]
        return plans

    def _load(self) -> None:
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                rows = json.load(handle)
            for row in rows:
                plan = Plan(id=row["id"], goal_id=row["goal_id"], title=row["title"],
                            status=row.get("status", "active"),
                            provider=row.get("provider"),
                            replanned=row.get("replanned", 0),
                            created=row.get("created", time.time()),
                            updated=row.get("updated", time.time()))
                plan.steps = [PlanStep(**step) for step in row.get("steps", [])]
                self._plans[plan.id] = plan
        except (ValueError, OSError, TypeError):
            self._plans = {}

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump([p.as_dict() for p in self._plans.values()], handle, indent=2)