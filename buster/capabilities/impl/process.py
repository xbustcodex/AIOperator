"""Process and system introspection capability."""

import os
import signal
import subprocess

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


class ProcessCapability(Capability):
    """List / kill processes and report system resource usage."""

    name = "process"
    actions_list = ["process.list", "process.kill", "system.info"]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        if ctx.action == "process.list":
            return CapabilityResult.ok(self._list_processes())
        if ctx.action == "process.kill":
            target = extra.get("pid")
            if target is None:
                return CapabilityResult.fail("Missing 'pid'")
            try:
                os.kill(int(target), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError) as exc:
                return CapabilityResult.fail(f"{type(exc).__name__}: {exc}")
            return CapabilityResult.ok({"killed": int(target)})
        if ctx.action == "system.info":
            return CapabilityResult.ok(self._system_info())
        return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")

    @staticmethod
    def _list_processes() -> list[dict]:
        processes = []
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/comm") as f:
                    name = f.read().strip()
                processes.append({"pid": int(entry), "name": name})
            except (OSError, ValueError):
                continue
        return processes

    @staticmethod
    def _system_info() -> dict:
        info = {"cpus": os.cpu_count()}
        try:
            meminfo = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    key, _, value = line.partition(":")
                    meminfo[key] = value.strip()
            info["memory"] = meminfo
        except OSError:
            pass
        try:
            path = os.getcwd()
            stat = os.statvfs(path)
            info["disk"] = {
                "free_bytes": stat.f_bavail * stat.f_frsize,
                "total_bytes": stat.f_blocks * stat.f_frsize,
            }
        except (OSError, AttributeError):
            pass
        return info