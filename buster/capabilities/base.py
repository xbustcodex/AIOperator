"""Base abstraction for Buster capabilities."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from buster.security.context import ExecutionContext, SecurityContext


@dataclass
class CapabilityContext:
    """Context passed to a capability invocation.

    Provides action identity, permission gating and shared state access.
    """

    action: str
    scope: Optional[str] = None
    extra: dict = field(default_factory=dict)
    execution: Optional[ExecutionContext] = None

    @property
    def actor(self) -> str:
        return (self.execution or ExecutionContext.from_inputs(self.action)).security.actor


@dataclass
class CapabilityResult:
    success: bool
    data: Any = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, data: Any = None) -> "CapabilityResult":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "CapabilityResult":
        return cls(success=False, error=error)


class Capability(ABC):
    """Base class for all Buster capabilities.

    Each concrete capability declares the actions it can serve and
    implements ``invoke``. Capabilities are registered with the kernel's
    CapabilityRegistry and only executed after a successful permission
    check and optional elevation.
    """

    name: str = "base"

    def __init__(self, kernel=None):
        self.kernel = kernel
        self.logger = logging.getLogger(f"buster.capabilities.{self.name}")

    @property
    @abstractmethod
    def actions(self) -> list[str]:
        """Actions this capability serves, e.g. ``["fs.read"]``."""

    @abstractmethod
    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        """Execute the action described by ``ctx``."""

    def close(self) -> None:
        """Release resources held by this capability. Default: no-op."""


class PermissionedCapability(Capability):
    """Capability whose every action is permission-gated by the kernel.

    Actions listed here require an explicit grant rather than falling back
    to the registry's default gate.
    """

    requires_permission: set = set()

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        if self.kernel is None:
            return CapabilityResult.fail("No kernel bound to capability")
        try:
            self.kernel.require(ctx.action, ctx.scope, {
                "actor": ctx.actor,
                **(ctx.extra or {}),
            })
        except PermissionError as exc:
            return CapabilityResult.fail(str(exc))
        return self.invoke_permitted(ctx)

    @abstractmethod
    def invoke_permitted(self, ctx: CapabilityContext) -> CapabilityResult:
        """Execute after the permission gate has accepted the action."""