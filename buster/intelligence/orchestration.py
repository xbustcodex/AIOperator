"""Cognitive orchestration for Buster OS.

Binds the full loop — perception → attention → world → memory → goals →
plan → agent/capability execution → observe → learn → reflect — onto the
existing single Kernel. A periodic scheduler job drives lightweight
cognition ticks; heavy work (planning, reflection, consolidation) only runs
when the rhythm says it is useful. No parallel loops, no second scheduler.
"""

import json
import logging

from buster.intelligence.agents import RoleAgent
from buster.intelligence.plans import PlanStep


class CognitiveOrchestrator:
    """Event-driven, resource-aware cognitive loop."""

    def __init__(self, kernel, cadence: float = 10.0):
        self.kernel = kernel
        self.cadence = cadence
        self._job = None
        self._subscriptions: list[tuple] = []
        self.logger = logging.getLogger("buster.intel.orchestrator")

    # -- lifecycle ------------------------------------------------

    def start(self) -> None:
        if self._job is not None:
            return
        router = self.kernel.event_router
        self._subscriptions = [
            ("capability.succeeded", lambda p: self.kernel.intel.nervous.touch()),
            ("capability.failed", self._on_failure),
            ("intel.signal", self._on_signal),
        ]
        for event_type, handler in self._subscriptions:
            try:
                router.subscribe(event_type, handler)
            except Exception:  # noqa: BLE001
                self.logger.exception("subscribe '%s' failed", event_type)
        self._job = self.kernel.scheduler.schedule(
            "cognition.tick", self.tick, every=self.cadence)
        self.logger.info("Cognitive orchestrator online (cadence=%ss)", self.cadence)
        self._record_world_facts()

    def stop(self) -> None:
        if self._job is not None:
            self.kernel.scheduler.cancel(self._job.id)
            self._job = None
        for event_type, handler in self._subscriptions:
            try:
                self.kernel.event_router.unsubscribe(event_type, handler)
            except Exception:  # noqa: BLE001
                pass
        self._subscriptions = []

    # -- passive tick -------------------------------------------------

    def tick(self, job=None) -> None:
        """One lightweight cognition pass (runs on the kernel scheduler)."""
        intel = self.kernel.intel
        snapshot = intel.nervous.snapshot()
        surfaced = intel.nervous.heed(snapshot)

        goals = [g.title for g in intel.goals.active()]
        nervous_state = intel.nervous.state(snapshot)
        intel.rhythm.transition(
            nervous_state, pending_goals=len(goals),
            active_jobs=self._active_job_count())
        state = intel.rhythm.current

        for signal in surfaced:
            intel.attention.note_signal(
                signal.kind, signal.level, signal.message,
                goals=goals, rhythm=state, details=signal.details)

        intel.proactive.tick()

        if intel.rhythm.should_consolidate():
            intel.memory.consolidate()
        if intel.rhythm.should_reflect():
            intel.reflection.reflect_now(reason="rhythm")

        self.kernel.world_model.record_event("cognition.tick", {"rhythm": state.value})

    def _active_job_count(self) -> int:
        try:
            return sum(1 for j in self.kernel.scheduler.list_jobs()
                       if j.status.value in ("pending", "running"))
        except Exception:  # noqa: BLE001
            return 0

    def _on_failure(self, payload: dict) -> None:
        self.kernel.intel.nervous.touch()
        if getattr(self.kernel, "event_router", None) is not None:
            self.kernel.event_router.emit("attention.note", {
                "kind": "capability", "level": "warning",
                "message": f"capability failed: {payload.get('action')}",
            })

    def _on_signal(self, payload: dict) -> None:
        intel = self.kernel.intel
        goals = [g.title for g in intel.goals.active()]
        intel.attention.note_signal(
            payload.get("kind"), payload.get("level"), payload.get("message"),
            goals=goals, rhythm=intel.rhythm.current)

    # -- active goal processing ---------------------------------------

    def process_goal(self, goal_text: str, kind: str = "user",
                     provider: str | None = None,
                     tentative: bool = False) -> dict:
        """Full cognitive loop for a goal. Bounded; always capability-based."""
        intel = self.kernel.intel
        intel.nervous.touch()

        goal = intel.goals.create(goal_text, kind=kind, provenance="user")
        if tentative:
            return {"goal_id": goal.id, "status": "accepted"}

        provider = self._resolve_provider(provider, goal_text)
        plan = intel.plans.create(goal_id=goal.id, title=goal.title, provider=provider)
        agent = RoleAgent(kernel=self.kernel, role="planner", max_steps=6)
        run = agent.run(goal.title, provider=provider)

        run_status = run.status.value
        materialized = [
            PlanStep(action=step.get("action") or "android.info", params={},
                     reason="planner",
                     status="succeeded" if step.get("success") else "failed",
                     observation=json.dumps(step, default=str)[:200])
            for step in run.history if step.get("phase") == "step"
        ]
        intel.plans.set_steps(plan.id, materialized)
        if run_status == "done":
            intel.goals.complete(goal.id)
            intel.plans.finish(plan.id, "completed")
            intel.reflection.trigger_after_goal(goal.id, "completed")
        else:
            intel.goals.fail(goal.id, blocker=run.error)
            intel.plans.finish(plan.id, "failed")
            self._replan_fix(goal.id, goal_text, provider, plan.id)
            intel.reflection.trigger_after_goal(goal.id, "failed")

        intel.learning.record_cycle(
            context="goal processing", intention=goal_text, action="planner",
            result=_SimpleResult(run_status == "done"),
            evaluation="success" if run_status == "done" else "failure")
        self.kernel.world_model.record_event(
            "goal.processed", {"goal_id": goal.id, "status": run_status})
        self.kernel.world_model.add_entity(goal.id, "goal",
                                           {"title": goal.title, "status": run_status})

        return {
            "goal_id": goal.id,
            "plan_id": plan.id,
            "status": run_status,
            "error": run.error,
            "steps": len([s for s in run.history if s.get("phase") == "step"]),
        }

    def _replan_fix(self, goal_id: str, goal_text: str, provider: str | None,
                    plan_id: str) -> None:
        """Bounded replanning after a failure (one remediation pass)."""
        intel = self.kernel.intel
        fixer = RoleAgent(kernel=self.kernel, role="fixer", max_steps=3)
        run = fixer.run(f"fix issues with: {goal_text}", provider=provider)
        if run.status.value == "done":
            steps = [PlanStep(action=a.get("action") or "android.info",
                              params={}, reason="fixer-remediation")
                     for a in run.history if a.get("phase") == "step"]
            intel.plans.append_steps(plan_id, steps)
            intel.plans.finish(plan_id, "completed")

    def _resolve_provider(self, provider: str | None, goal_text: str) -> str:
        if provider:
            return provider
        try:
            return self.kernel.intel.providers.select(goal_text)
        except Exception:  # noqa: BLE001
            return "local"

    def _record_world_facts(self) -> None:
        try:
            self.kernel.world_model.observe("cognition.cadence", self.cadence,
                                            source="orchestrator")
            self.kernel.world_model.observe(
                "host", self.kernel.perception.snapshot().get("device", {}).get("host", "unknown"),
                source="perception")
        except Exception:  # noqa: BLE001
            pass

    def state(self) -> dict:
        return {
            "cadence": self.cadence,
            "tick_scheduled": self._job is not None,
            "plans": len(self.kernel.intel.plans.list_plans(status="active")),
        }


class _SimpleResult:
    def __init__(self, success: bool):
        self.success = success
        self.error = None