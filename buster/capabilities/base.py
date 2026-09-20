"""Base abstraction for Buster capabilities."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CapabilityContext:
    """Context passed to a capability invocation.

    Provides action identity, permission gating and shared state access.
    """
    action: str
    scope: Optional[str] = None
    extra: dict = field(default_factory=dict)


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
    check.
    """

    name: str = "base"

    def __init__(self, kernel=None):
        self.kernel = kernel
        self.logger = logging.getLogger(f"buster.capabilities.{self.name}")

    @property
    @abstractmethod
    def actions(self) -> list[str]:
        """Actions this capability serves, e.g. ``["file.read"]``."""

    @abstractmethod
    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        """Execute the action described by ``ctx``."""

    def close(self) -> None:
        """Release resources held by this capability. Default: no-op."""