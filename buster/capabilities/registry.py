"""Capability registry and dispatcher."""

import logging
from typing import Optional

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


class CapabilityNotFoundError(Exception):
    pass


class CapabilityRegistry:
    """Registers capabilities and routes capability calls to their owner."""

    def __init__(self, kernel=None):
        self._capabilities: dict[str, Capability] = {}
        self._action_map: dict[str, str] = {}
        self.logger = logging.getLogger("buster.capabilities.registry")

    def register(self, capability: Capability) -> None:
        if capability.name in self._capabilities:
            raise ValueError(f"Capability '{capability.name}' already registered")
        self._capabilities[capability.name] = capability
        for action in capability.actions:
            self._action_map[action] = capability.name
        self.logger.info("Registered capability '%s'", capability.name)

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

    def call(self, action: str, scope: Optional[str] = None,
             extra: Optional[dict] = None, context: Optional[dict] = None) -> CapabilityResult:
        capability = self.find_capability(action)
        if capability is None:
            return CapabilityResult.fail(f"No capability provides action '{action}'")

        gating_context = dict(context or {})
        gating_context.update(extra or {})
        if capability.kernel is not None:
            try:
                capability.kernel.require(action, scope, gating_context)
            except PermissionError as exc:
                return CapabilityResult.fail(str(exc))

        ctx = CapabilityContext(action=action, scope=scope, extra=extra or {})
        return capability.invoke(ctx)

    def list_capabilities(self) -> list[str]:
        return sorted(self._capabilities.keys())

    def shutdown(self) -> None:
        for name in list(self._capabilities):
            try:
                self._capabilities[name].close()
            except Exception:  # noqa: BLE001
                self.logger.exception("Error closing capability '%s'", name)
            del self._capabilities[name]
        self._action_map.clear()