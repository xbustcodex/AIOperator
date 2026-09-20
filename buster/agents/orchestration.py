"""Agent orchestration: goal -> plan -> capability actions -> result."""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from buster.agents.base import Agent, AgentRun, AgentStatus
from buster.ai_providers.base import AIMessage, AIProvider


@dataclass
class PlanAction:
    action: str
    params: dict = field(default_factory=dict)
    reason: str = ""


class AgentOrchestrator(Agent):
    """Drives an AI provider to translate a goal into capability calls.

    The loop is bounded by ``max_steps`` and each step is executed through
    the kernel capability registry, so permission checks and event
    lifecycle apply exactly as for interactive use.
    """

    name = "orchestrator"

    def __init__(self, kernel=None):
        super().__init__(kernel=kernel)
        self.max_steps = 10
        self.system_prompt = (
            "You are the Buster OS orchestrator. Produce a compact, structured "
            "plan to satisfy the user's goal. Respond only with a JSON array of "
            "objects: [{\"action\": \"<capability.action>\", \"params\": {...}, "
            "\"reason\": \"why\"}]. Use only actions available in the capability "
            "registry."
        )

    def run(self, target: str, **kwargs) -> AgentRun:
        run = AgentRun(target=target)
        run.started_at = __import__("time").time()

        provider: Optional[AIProvider] = None
        if self.kernel is not None:
            try:
                provider = self.kernel.ai.providers.get(kwargs.get("provider"))
            except Exception:  # noqa: BLE001
                provider = None

        run.status = AgentStatus.RUNNING
        try:
            plan = self._plan(target, provider)
            run.history.append({"phase": "plan", "plan": [p.__dict__ for p in plan]})
            executed = []
            for step in plan[: self.max_steps]:
                if self.kernel is None:
                    break
                result = self.kernel.cap.call(
                    step.action,
                    context={"actor": f"agent:{self.name}", "agent": self.name, "goal": target},
                    **({"extra": step.params} if step.params else {}),
                )
                executed.append({"action": step.action, "success": result.success,
                                 "data": result.data, "error": result.error})
                run.history.append({"phase": "step", "action": step.action, "result": result.success})
            run.result = {"plan": [p.__dict__ for p in plan], "executed": executed}
            run.status = AgentStatus.DONE
        except Exception as exc:  # noqa: BLE001
            run.error = str(exc)
            run.status = AgentStatus.FAILED
        finally:
            run.finished_at = __import__("time").time()
            self._record_experience(run)
        return run

    def _plan(self, goal: str, provider: Optional[AIProvider]) -> list[PlanAction]:
        if provider is None:
            return [PlanAction(action="android.info", reason="introspect device to ground the goal")]
        conversation = [
            AIMessage(role="system", content=self.system_prompt),
            AIMessage(role="user", content=f"Goal: {goal}\nAvailable actions: "
                       f"{self._available_actions()}"),
        ]
        completion = provider.complete(conversation)
        return self._parse_plan(completion.message.content, goal)

    def _parse_plan(self, content: str, goal: str) -> list[PlanAction]:
        try:
            cleaned = content.strip()
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            rows = json.loads(cleaned)
        except (ValueError, json.JSONDecodeError):
            return [PlanAction(action="android.info", reason=f"fallback for '{goal}'")]
        plan = []
        for row in rows:
            action = row.get("action", "")
            if not self._known_action(action):
                continue
            plan.append(PlanAction(action=action, params=row.get("params") or {},
                                   reason=row.get("reason", "")))
        return plan or [PlanAction(action="android.info", reason="fallback for '{goal}'")]

    def _known_action(self, action: str) -> bool:
        if self.kernel is None:
            return True
        return self.kernel.cap.find_capability(action) is not None

    def _available_actions(self) -> str:
        if self.kernel is None:
            return ""
        return ", ".join(self.kernel.cap.list_actions())

    def _record_experience(self, run: AgentRun) -> None:
        if self.kernel is None or getattr(self.kernel, "memory", None) is None:
            return
        try:
            self.kernel.memory.experience.record({
                "target": run.target,
                "status": run.status.value,
                "result": run.result,
                "error": run.error,
                "steps": len(run.history),
            })
        except Exception:  # noqa: BLE001
            pass