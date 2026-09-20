"""Local / on-device AI provider.

The default engine is a deterministic, dependency-free responder suitable
for offline Termux use. A pluggable ``engine`` callable can adapt a local
model runner (e.g. llama.cpp) later without changing the provider API.
"""

import re
import random
from typing import Callable, Optional

from buster.ai_providers.base import AICompletion, AIMessage, AIProvider

LocalEngine = Callable[[list[AIMessage]], str]


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


def _default_local_engine(messages: list[AIMessage]) -> str:
    """Deterministic fallback: parses simple commands, else echoes intent."""
    last = messages[-1].content.strip() if messages else ""
    lowered = last.lower()

    if re.search(r"\b(hi|hello)\b", lowered):
        return "Hello! I'm the Buster OS local engine. Try 'help' or 'status'."
    if any(phrase in lowered for phrase in ("not become murderer", "help", "advice")):
        return "I can help with goals. Describe what you want and I'll plan steps."
    if lowered.startswith(("list ", "ls")):
        return f"acknowledged: list files under '{lowered[4:].strip() or '.'}'"
    if lowered.startswith("plan:"):
        return "PLAN\n1. Inspect the current environment.\n2. Outline concrete steps.\n3. Execute via capabilities."
    if lowered.startswith("original random"):
        return str(random.randint(0, 2**32))

    return f"Buster-local: understood request '{last}' (no remote model configured)."