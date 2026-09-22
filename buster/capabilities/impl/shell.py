"""Shell execution capability (local subprocess)."""

import shlex
import subprocess
from typing import Optional

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


def _run_command(cmd: str, cwd: Optional[str] = None, timeout: Optional[float] = None) -> dict:
    completed = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


class ShellCapability(Capability):
    """Run commands through the system shell (TerminalP ``/bin/sh``)."""

    name = "shell"
    actions_list = ["shell.run", "shell.check"]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        cmd = extra.get("command")
        if not cmd:
            return CapabilityResult.fail("Missing 'command'")
        try:
            result = _run_command(cmd, cwd=extra.get("cwd"), timeout=extra.get("timeout"))
        except subprocess.TimeoutExpired:
            return CapabilityResult.fail(f"Command timed out: {cmd[:80]}")
        except OSError as exc:
            return CapabilityResult.fail(f"OSError: {exc}")

        if ctx.action == "shell.check" and result["exit_code"] != 0:
            return CapabilityResult.fail(
                f"Command failed ({result['exit_code']}): {result['stderr']}"
            )
        return CapabilityResult.ok(result)