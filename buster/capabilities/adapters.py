"""Compatibility adapters for the capability system.

These adapters let existing or third-party code be surfaced as first-class
capabilities without rewriting:

* ``FunctionCapability`` - wrap any ``fn(ctx) -> CapabilityResult``.
* ``LegacyRouterAdapter`` - adapt a legacy ``{action: handler}`` router
  (AIOperator-style) into capabilities, preserving its call convention.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult

Handler = Callable[[CapabilityContext], CapabilityResult]
LegacyHandler = Callable[[dict], Any]


class FunctionCapability(Capability):
    """Adapt a plain function into a Capability.

    ``handler`` receives the CapabilityContext and returns a
    CapabilityResult (or a plain value, coerced to ``CapabilityResult.ok``).
    """

    def __init__(self, name: str, handler: Callable[[CapabilityContext], Any],
                 action_list: list[str], kernel: object = None):
        super().__init__(kernel=kernel)
        self.name = name
        self.handler = handler
        self.action_list = action_list
        self.logger = logging.getLogger(f"buster.capabilities.{self.name}")

    @property
    def actions(self) -> list[str]:
        return self.action_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        result = self.handler(ctx)
        if isinstance(result, CapabilityResult):
            return result
        return CapabilityResult.ok(result)


class LegacyRouterAdapter(Capability):
    """Expose a legacy ``{action: handler(dict) -> dict}`` router.

    Legacy handlers receive ``{"action": ..., "params": ..., "context": ...}``
    and return a dict. Results are normalized into CapabilityResult.
    """

    name = "legacy"

    def __init__(self, router: Dict[str, LegacyHandler], kernel=None, name: str = "legacy"):
        super().__init__(kernel=kernel)
        self._router = router
        self.name = name
        self.logger = logging.getLogger(f"buster.capabilities.{self.name}")

    @property
    def actions(self) -> list[str]:
        return list(self._router.keys())

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        handler = self._router.get(ctx.action)
        if handler is None:
            return CapabilityResult.fail(f"No legacy handler for '{ctx.action}'")
        try:
            outcome = handler({
                "action": ctx.action,
                "params": dict(ctx.extra or {}),
                "context": ctx.execution.as_dict() if ctx.execution else {},
            })
        except Exception as exc:  # noqa: BLE001
            return CapabilityResult.fail(f"Legacy handler raised: {exc}")
        if isinstance(outcome, dict) and "success" in outcome:
            return CapabilityResult(
                success=bool(outcome["success"]),
                data=outcome.get("data"),
                error=outcome.get("error"),
            )
        return CapabilityResult.ok(outcome)