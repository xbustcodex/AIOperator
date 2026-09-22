"""Package management introspection capability.

Reads read-only package-system facts. The host package manager remains the
Termux-class ``pkg`` binary (also used by TerminalP); command invocation is
preserved while the reporting vocabulary is host-agnostic.
"""

import subprocess
import sys

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


class PackageCapability(Capability):
    """Read-only package system facts (runtime / pip / host pkg)."""

    name = "pkg"
    actions_list = ["pkg.info", "pkg.list"]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        if ctx.action == "pkg.info":
            return CapabilityResult.ok(self._info())
        if ctx.action == "pkg.list":
            return CapabilityResult.ok(self._list_pip())
        return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")

    @staticmethod
    def _info() -> dict:
        info = {
            "python_version": sys.version.split()[0],
            "python_impl": sys.implementation.name if hasattr(sys, "implementation") else "",
            "executable": sys.executable,
        }
        host_packages = _host_pkg_list()
        if host_packages is not None:
            info["host_packages_count"] = len(host_packages)
            info["host_packages"] = host_packages
        return info

    @staticmethod
    def _list_pip() -> list[dict]:
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=15,
            )
            if completed.returncode != 0:
                return []
            import json
            rows = json.loads(completed.stdout)
            return [{"name": r["name"], "version": r["version"]} for r in rows]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return []


def _host_pkg_list() -> list[str] | None:
    try:
        completed = subprocess.run(
            ["pkg", "list-installed"], capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    names = [line.split("/")[0] if "/" in line else line.split()[0] for line in lines]
    return names[:200]