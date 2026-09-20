"""Capability system for Buster OS."""

from buster.capabilities.adapters import FunctionCapability, LegacyRouterAdapter
from buster.capabilities.base import (
    Capability,
    CapabilityContext,
    CapabilityResult,
    PermissionedCapability,
)
from buster.capabilities.registry import CapabilityNotFoundError, CapabilityRegistry

__all__ = [
    "Capability",
    "CapabilityContext",
    "CapabilityNotFoundError",
    "CapabilityRegistry",
    "CapabilityResult",
    "FunctionCapability",
    "LegacyRouterAdapter",
    "PermissionedCapability",
]