"""Local / on-device AI provider.

The default engine is a deterministic, dependency-free responder suitable
for offline TerminalP use. When ``plan_engine=True`` (or a planning prompt is
detected) it emits a single JSON action suitable for the PlannerAgent's
think/act/observe loop. A pluggable ``engine`` callable can adapt a local
model runner (e.g. llama.cpp) later without changing the provider API.
"""

import json
import re

from typing import Callable, Optional

from buster.ai_providers.base import AICompletion, AIMessage, AIProvider

LocalEngine = Callable[[list[AIMessage]], str]

_ACTION_RE = re.compile(r"\{[^{}]*\"action\"[^{}]*\}", re.DOTALL)
_PLAN_TRIGGERS = ("return the next action", "output the next action",
                  "next action as json", "think step", "act as json")


def _default_local_engine(messages: list[AIMessage]) -> str:
    """Deterministic fallback: planning prompts get JSON actions, else intent."""
    last = messages[-1].content.strip() if messages else ""
    lowered = last.lower()

    if any(trigger in lowered for trigger in _PLAN_TRIGGERS):
        return _fallback_plan_step(last)
    if re.search(r"\b(hi|hello)\b", lowered):
        return "Hello! I'm the Buster OS local engine. Try 'help', 'status' or 'think <goal>'."
    if lowered.startswith(("list ", "ls")):
        return f"acknowledged: list files under '{lowered[4:].strip() or '.'}'"
    if lowered.startswith("plan:"):
        return "PLAN\n1. Inspect the current environment.\n2. Outline concrete steps.\n3. Execute via capabilities."
    return f"Buster-local: understood request '{last}' (no remote model configured)."


def _fallback_plan_step(goal_text: str) -> str:
    """Return a safe, known JSON action as the next plan step."""
    lowered = goal_text.lower()
    if "inspect" in lowered or "environment" in lowered or "device" in lowered:
        action, params = "android.info", {}
    elif "list" in lowered or "files" in lowered:
        action, params = "fs.list", {"path": "."}
    elif "time" in lowered:
        action, params = "time.now", {}
    elif "status" in lowered or "kernel" in lowered:
        action, params = "process.list", {}
    else:
        action, params = "android.info", {}
    return json.dumps({"action": action, "params": params,
                       "reason": "local fallback plan step"})


class LocalProvider(AIProvider):
    """On-device provider with a pluggable text engine."""

    name = "local"

    def __init__(self, engine: Optional[LocalEngine] = None, model: str = "buster-local", **options):
        super().__init__(**options)
        self._engine = engine or _default_local_engine
        self._model = model
        self.logger.info("LocalAI provider ready (model=%s)", model)

    def complete(self, messages: list[AIMessage], **kwargs) -> AICompletion:
        text = self._engine(messages)
        return AICompletion(
            message=AIMessage(role="assistant", content=text),
            model=self._model,
            usage={"engine": "local", "messages": len(messages)},
        )

    def models(self) -> list[str]:
        return [self._model]