"""Terminal capability: interactive-style command streaming.

A thin wrapper over a persistent subprocess with streaming I/O. Falls back
to one-shot execution when streaming is unavailable.
"""

import shlex
import subprocess

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


class TerminalCapability(Capability):
    """Interactive terminal sessions with streaming output capture."""

    name = "terminal"
    actions_list = ["terminal.open", "terminal.write", "terminal.close", "terminal.run"]

    def __init__(self, kernel=None):
        super().__init__(kernel=kernel)
        self._process = None

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        handler = getattr(self, f"_on_{ctx.action.replace('.', '_')}", None)
        if handler is None:
            return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")
        return handler(ctx.extra or {})

    def _on_terminal_open(self, extra: dict) -> CapabilityResult:
        if self._process is not None:
            return CapabilityResult.fail("Terminal already open")
        self._process = subprocess.Popen(
            extra.get("shell", "/bin/sh"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        return CapabilityResult.ok({"pid": self._process.pid, "shell": "/bin/sh"})

    def _on_terminal_write(self, extra: dict) -> CapabilityResult:
        if self._process is None:
            return CapabilityResult.fail("No open terminal")
        try:
            self._process.stdin.write(shlex.join([extra.get("input", "")]) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            self._close()
            return CapabilityResult.fail(f"{type(exc).__name__}: {exc}")
        return CapabilityResult.ok({"sent": extra.get("input")})

    def _on_terminal_close(self, extra: dict) -> CapabilityResult:
        if self._process is None:
            return CapabilityResult.fail("No open terminal")
        self._close()
        return CapabilityResult.ok({"closed": True})

    def _on_terminal_run(self, extra: dict) -> CapabilityResult:
        import subprocess as sp
        try:
            completed = sp.run(
                extra.get("command", ""),
                shell=True,
                capture_output=True,
                text=True,
                timeout=extra.get("timeout"),
            )
            return CapabilityResult.ok({
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            })
        except sp.TimeoutExpired:
            return CapabilityResult.fail("Command timed out")

    def _close(self) -> None:
        if self._process is None:
            return
        for stream in (self._process.stdin, self._process.stdout, self._process.stderr):
            try:
                stream.close()
            except OSError:
                pass
        self._process.terminate()
        self._process = None

    def close(self) -> None:
        self._close()