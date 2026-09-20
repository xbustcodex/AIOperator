"""Git capability backed by the system ``git`` binary."""

import subprocess
from typing import Optional

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


def _git(args: list[str], cwd: Optional[str] = None) -> dict:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


class GitCapability(Capability):
    """Wrapper around common git workflows."""

    name = "git"
    actions_list = [
        "git.status", "git.log", "git.branch",
        "git.clone", "git.add", "git.commit", "git.pull",
    ]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        handler = getattr(self, f"_on_{ctx.action.replace('.', '_')}", None)
        if handler is None:
            return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")
        return handler(ctx.extra or {})

    def _base(self, extra: dict) -> Optional[str]:
        return extra.get("cwd") or extra.get("repo")

    def _on_git_status(self, extra: dict) -> CapabilityResult:
        result = _git(["status", "--porcelain"], cwd=self._base(extra))
        return CapabilityResult.ok(result)

    def _on_git_log(self, extra: dict) -> CapabilityResult:
        result = _git(["log", "--oneline", "-n", str(extra.get("limit", 20))], cwd=self._base(extra))
        return CapabilityResult.ok(result)

    def _on_git_branch(self, extra: dict) -> CapabilityResult:
        result = _git(["branch", "-a"], cwd=self._base(extra))
        return CapabilityResult.ok(result)

    def _on_git_clone(self, extra: dict) -> CapabilityResult:
        url = extra.get("url")
        target = extra.get("target")
        result = _git(["clone", url, target], cwd=extra.get("cwd"))
        return CapabilityResult.ok(result)

    def _on_git_add(self, extra: dict) -> CapabilityResult:
        result = _git(["add", "-A"], cwd=self._base(extra))
        return CapabilityResult.ok(result)

    def _on_git_commit(self, extra: dict) -> CapabilityResult:
        message = extra.get("message", "")
        result = _git(["commit", "-m", message], cwd=self._base(extra))
        return CapabilityResult.ok(result)

    def _on_git_pull(self, extra: dict) -> CapabilityResult:
        result = _git(["pull", "--ff-only"], cwd=self._base(extra))
        return CapabilityResult.ok(result)