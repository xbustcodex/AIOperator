"""Deliberate planner agent: think -> act -> observe -> reflect.

Runs a bounded loop against an AI provider. Each step asks the provider for
the next action (as a single JSON object), executes it through the kernel
capability registry (permissions, elevation, events, audit all apply), feeds
the observation back, and finally distils the run into experience memory and
learned knowledge via the reflection engine.
"""

import json
import logging
import re
import time
from typing import Optional

from buster.agents.base import Agent, AgentRun, AgentStatus
from buster.ai_providers.base import AIMessage, AIProvider

_ACTION_RE = re.compile(r"\{[^{}]*\"action\"[^{}]*\}", re.DOTALL)


class PlannerAgent(Agent):
    """Goal-directed think/act/observe loop driven by an AI provider."""

    name = "planner"

    def __init__(self, kernel=None, max_steps: int = 8):
        super().__init__(kernel=kernel)
        self.max_steps = max_steps

    # -- main loop -----------------------------------------------------

    def run(self, target: str, **kwargs) -> AgentRun:
        run = AgentRun(target=target)
        run.started_at = time.time()
        run.status = AgentStatus.RUNNING

        provider = self._resolve_provider(kwargs.get("provider"))
        transcript = self._build_transcript(target, provider)

        try:
            for _ in range(max(self.max_steps, 1)):
                reply = self._ask(provider, transcript, target)
                if reply is None:
                    break
                transcript.append(AIMessage(role="assistant", content=reply))

                if self._is_finished(reply):
                    run.history.append({"phase": "step", "action": "done"})
                    break

                action, params = self._parse_action(reply, target)
                if action is None:
                    continue

                result = self._execute(action, params, target)
                run.history.append({"phase": "step", "action": action,
                                    "success": result.success})
                observation = self._observation(result)
                transcript.append(AIMessage(role="user", content=observation))

            run.result = {"steps": [h for h in run.history if h.get("phase") == "step"]}
            run.status = AgentStatus.DONE
        except Exception as exc:  # noqa: BLE001
            run.error = str(exc)
            run.status = AgentStatus.FAILED
        finally:
            run.finished_at = time.time()
            self._learnt_from(run)
        return run

    # -- provider ------------------------------------------------------

    def _resolve_provider(self, name: Optional[str]) -> Optional[AIProvider]:
        if self.kernel is None:
            return None
        try:
            return self.kernel.ai.providers.get(name)
        except Exception:  # noqa: BLE001
            return None

    def _build_transcript(self, target: str,
                          provider: Optional[AIProvider]) -> list[AIMessage]:
        system = (
            "You are the Buster OS planner. You solve the user's goal by "
            "emitting ONE step at a time as a single JSON object: "
            '{"action": "<capability.action>", "params": {...}, "reason": "..."}. '
            "After each user observation, emit the next step. When the goal is "
            "satisfied, reply with exactly: DONE."
            "\n\nAvailable actions:\n" + self._available_actions() +
            "\n\nEnvironment:\n" + self._environment_context() +
            "\n\nLearned knowledge that may help:\n" + self._knowledge_context()
        )
        return [
            AIMessage(role="system", content=system),
            AIMessage(role="user", content=f"Goal: {target}"),
        ]

    def _ask(self, provider: Optional[AIProvider],
             transcript: list[AIMessage], goal: str) -> Optional[str]:
        if provider is not None:
            try:
                return provider.complete(transcript).message.content
            except Exception:  # noqa: BLE001
                pass
        return _fallback_ask(goal, transcript)

    # -- action handling ----------------------------------------------

    @staticmethod
    def _is_finished(reply: str) -> bool:
        return "DONE" in reply.upper()

    def _parse_action(self, reply: str, goal: str) -> tuple[Optional[str], dict]:
        match = _ACTION_RE.search(reply)
        if match:
            try:
                step = json.loads(match.group(0))
                action = step.get("action")
                params = step.get("params") or {}
                if action and self._known_action(action):
                    return action, params
            except ValueError:
                pass
        return None, {}

    def _known_action(self, action: str) -> bool:
        if self.kernel is None:
            return True
        return self.kernel.cap.find_capability(action) is not None

    def _execute(self, action: str, params: dict, goal: str):
        actor = f"agent:{self.name}"
        ctx = {"actor": actor, "agent": self.name, "goal": goal}
        return self.kernel.cap.call(action, extra=params or None, context=ctx)

    # -- observations / context ---------------------------------------

    @staticmethod
    def _observation(result) -> str:
        preview = json.dumps(result.data, default=str)
        if len(preview) > 500:
            preview = preview[:500] + "..."
        return f"action result (success={result.success}): {preview or '(no data)'}"

    def _available_actions(self) -> str:
        if self.kernel is None:
            return ""
        return ", ".join(self.kernel.cap.list_actions())

    def _environment_context(self) -> str:
        if self.kernel is None:
            return ""
        facts = self.kernel.world_model.facts()
        return ", ".join(f"{k}={v}" for k, v in facts.items())[:600] or "none"

    def _knowledge_context(self) -> str:
        if self.kernel is None:
            return ""
        entries = self.kernel.memory.knowledge.entries()
        preview = [f"{e['key']}: {e['value']}" for e in entries[:8]]
        return "\n".join(preview) or "none"

    # -- learning ------------------------------------------------------

    def _learnt_from(self, run: AgentRun) -> None:
        if self.kernel is None or getattr(self.kernel, "memory", None) is None:
            return
        entry = {
            "target": run.target,
            "status": run.status.value,
            "error": run.error,
            "steps": len(run.history),
            "result": run.result,
            "agent": self.name,
        }
        try:
            self.kernel.memory.experience.record(entry)
            if getattr(self.kernel.memory, "reflection", None) is not None:
                self.kernel.memory.reflection.on_experience(entry)
        except Exception:  # noqa: BLE001
            self.logger.exception("Planner learning failed")


def _fallback_ask(goal: str, transcript: list[AIMessage]) -> str:
    """Rule-based single action when no provider is reachable."""
    from buster.ai_providers.local import _fallback_plan_step
    return _fallback_plan_step(goal)