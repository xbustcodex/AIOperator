"""Capability registry, dispatcher and event lifecycle."""

import logging
import time
from typing import Optional

from buster.capabilities.base import (
    Capability,
    CapabilityContext,
    CapabilityResult,
)
from buster.security.context import ExecutionContext

EVENT_CALLING = "capability.calling"
EVENT_SUCCEEDED = "capability.succeeded"
EVENT_FAILED = "capability.failed"


class CapabilityNotFoundError(Exception):
    pass


class CapabilityRegistry:
    """Registers capabilities and routes calls to their owner.

    Every dispatch runs through the full lifecycle:

    1. locate capability,
    2. build ExecutionContext,
    3. emit ``capability.calling``,
    4. permission gate + optional elevation,
    5. invoke the capability,
    6. emit ``capability.succeeded`` / ``capability.failed``,
    7. audit the outcome when the kernel exposes one.
    """

    def __init__(self, kernel=None):
        self._capabilities: dict[str, Capability] = {}
        self._action_map: dict[str, str] = {}
        self.kernel = kernel
        self.logger = logging.getLogger("buster.capabilities.registry")

    # -- registration --------------------------------------------------

    def register(self, capability: Capability) -> None:
        if capability.name in self._capabilities:
            raise ValueError(f"Capability '{capability.name}' already registered")
        self._capabilities[capability.name] = capability
        for action in capability.actions:
            self._action_map[action] = capability.name
        self.logger.info("Registered capability '%s'", capability.name)
        self._emit("capability.registered", {
            "name": capability.name, "actions": capability.actions,
        })

    def unregister(self, name: str) -> None:
        capability = self._capabilities.pop(name, None)
        if capability is None:
            raise CapabilityNotFoundError(f"Unknown capability '{name}'")
        for action, owner in list(self._action_map.items()):
            if owner == name:
                del self._action_map[action]
        capability.close()

    def get(self, name: str) -> Optional[Capability]:
        return self._capabilities.get(name)

    def find_capability(self, action: str) -> Optional[Capability]:
        owner = self._action_map.get(action)
        return self._capabilities.get(owner) if owner else None

    # -- dispatch ------------------------------------------------------

    def call(self, action: str, scope: Optional[str] = None,
             extra: Optional[dict] = None, context: Optional[dict] = None) -> CapabilityResult:
        capability = self.find_capability(action)
        if capability is None:
            return CapabilityResult.fail(f"No capability provides action '{action}'")

        execution = ExecutionContext.from_inputs(
            action=action, scope=scope, context=context,
        )

        self._emit(EVENT_CALLING, {"action": action, **(execution.as_dict())})

        # Permission gate (inherited permissioned path or default gate).
        gating_context = dict(execution.as_dict())
        gating_context.update(extra or {})
        if self.kernel is not None:
            decision = self.kernel.permissions.check(action, scope, gating_context)
            if not decision.allowed:
                if self.kernel.security.elevation.requires_elevation(action) and \
                        self.kernel.security.elevation.approve(action, execution.as_dict()):
                    pass
                else:
                    error = f"Permission denied for action '{action}': {decision.reason}"
                    return self._finish_failure(action, capability, error, execution)

        ctx = CapabilityContext(action=action, scope=scope, extra=extra or {}, execution=execution)
        try:
            result = capability.invoke(ctx)
        except Exception as exc:  # noqa: BLE001 - unify capability failures
            return self._finish_failure(action, capability, f"{type(exc).__name__}: {exc}", execution)

        if not isinstance(result, CapabilityResult):
            result = CapabilityResult.ok(result)

        if result.success:
            return self._finish_success(action, capability, result, execution)
        return self._finish_failure(action, capability, result.error or "capability failed", execution)

    def run_async(self, action: str, scope: Optional[str] = None,
                  extra: Optional[dict] = None, context: Optional[dict] = None) -> object:
        """Schedule a capability call on the kernel scheduler as a job."""
        if self.kernel is None:
            raise CapabilityNotFoundError("Registry not bound to a kernel; cannot schedule")
        return self.kernel.scheduler.schedule(
            name=f"cap.{action}",
            func=lambda job: self.call(action, scope, extra, context),
        )

    # -- lifecycle helpers ---------------------------------------------

    def _finish_success(self, action, capability, result, execution) -> CapabilityResult:
        self._emit(EVENT_SUCCEEDED, {"action": action, "capability": capability.name})
        self._audit("capability.succeeded", action, execution, {"time_ms": None})
        return result

    def _finish_failure(self, action, capability, error, execution) -> CapabilityResult:
        self._emit(EVENT_FAILED, {"action": action, "capability": capability.name, "error": error})
        self._audit("capability.failed", action, execution, {"error": error})
        return CapabilityResult(success=False, data=None, error=error)

    def _audit(self, kind: str, action: str, execution: ExecutionContext, detail: dict) -> None:
        if self.kernel is not None and getattr(self.kernel, "audit", None) is not None:
            self.kernel.audit.record(kind, execution.security.actor,
                                     {"action": action, "scope": execution.security.scope, **detail})

    def _emit(self, event_type: str, payload: dict) -> None:
        if self.kernel is not None and getattr(self.kernel, "event_router", None) is not None:
            if self.kernel.event_router.running:
                self.kernel.event_router.emit(event_type, payload)

    # -- listing / shutdown --------------------------------------------

    def list_capabilities(self) -> list[str]:
        return sorted(self._capabilities.keys())

    def list_actions(self) -> list[str]:
        return sorted(self._action_map.keys())

    def shutdown(self) -> None:
        for name in list(self._capabilities):
            try:
                self._capabilities[name].close()
            except Exception:  # noqa: BLE001
                self.logger.exception("Error closing capability '%s'", name)
            del self._capabilities[name]
        self._action_map.clear()