"""Command registry and dispatch for the interactive shell."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from buster.shell.parser import Command
from buster.shell.results import StructuredResult

if TYPE_CHECKING:
    from buster.shell.session import InteractiveShell

Handler = Callable[["InteractiveShell", Command], StructuredResult]


@dataclass
class CommandSpec:
    name: str
    handler: Handler
    help: str = ""


class CommandRegistry:
    """Owns shell command handlers and resolves dispatch targets."""

    def __init__(self):
        self._commands: dict[str, CommandSpec] = {}
        self._aliases: dict[str, str] = {}
        self.logger = logging.getLogger("buster.shell.registry")

    def register(self, name: str, handler: Handler, help: str = "") -> None:
        self._commands[name] = CommandSpec(name=name, handler=handler, help=help)

    def alias(self, alias: str, target: str) -> None:
        self._aliases[alias] = target

    def has(self, name: str) -> bool:
        return name in self._commands or name in self._aliases

    def resolve(self, name: str) -> CommandSpec | None:
        name = self._aliases.get(name, name)
        return self._commands.get(name)

    def dispatch(self, shell: "InteractiveShell", command: Command) -> StructuredResult:
        spec = self.resolve(command.name)
        if spec is None:
            return StructuredResult.failure(command.name, f"unknown command '{command.name}'")
        try:
            return spec.handler(shell, command)
        except Exception as exc:  # noqa: BLE001 - a command must never crash the shell
            return StructuredResult.failure(command.name, f"{type(exc).__name__}: {exc}")

    def names(self) -> list[str]:
        return sorted(self._commands.keys())