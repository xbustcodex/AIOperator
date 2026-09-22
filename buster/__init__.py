"""Buster OS - AI-native operating environment for TerminalP on Android.

Buster OS provides a unified runtime for AI agents on mobile devices,
encompassing an event bus, scheduler, capability system, memory subsystem,
perception and Android integration. TerminalP is the first-class phone host;
Termux-class Android terminals remain supported for compatibility.
"""

from buster.version import VERSION, __version__, get_version

__all__ = ["VERSION", "__version__", "get_version"]