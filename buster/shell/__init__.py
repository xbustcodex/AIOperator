"""Interactive shell subsystem for Buster OS."""

from buster.shell.parser import Command, parse
from buster.shell.registry import CommandRegistry
from buster.shell.results import StructuredResult
from buster.shell.session import InteractiveShell

__all__ = [
    "Command",
    "CommandRegistry",
    "InteractiveShell",
    "StructuredResult",
    "parse",
]