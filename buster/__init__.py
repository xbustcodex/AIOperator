"""Buster OS - AI-native operating environment for Termux on Android.

Buster OS provides a unified runtime for AI agents on mobile devices,
encompassing an event bus, scheduler, capability system, memory subsystem,
perception and Android integration.
"""

from buster.version import VERSION, __version__, get_version

__all__ = ["VERSION", "__version__", "get_version"]