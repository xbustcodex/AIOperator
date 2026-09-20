"""Capability system for Buster OS."""

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult
from buster.capabilities.registry import CapabilityRegistry

__all__ = [
    "Capability",
    "CapabilityContext",
    "CapabilityRegistry",
    "CapabilityResult",
]