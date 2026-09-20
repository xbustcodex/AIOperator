"""Android / Termux capability.

Reads device facts locally and optionally shells out to ``termux-api``
commands when available (battery, sensors). All data collectors degrade
gracefully.
"""

import os
import subprocess

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult
from buster.android_integration.device import device_info


def _termux_api(args: list[str]) -> dict | None:
    try:
        completed = subprocess.run(
            ["termux-api", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return {"exit_code": completed.returncode, "stdout": completed.stdout}
    except (OSError, subprocess.TimeoutExpired):
        return None


class AndroidCapability(Capability):
    """Android environment introspection."""

    name = "android"
    actions_list = ["android.info", "android.battery", "android.sensors"]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        if ctx.action == "android.info":
            return CapabilityResult.ok(device_info().__dict__)
        if ctx.action == "android.battery":
            out = _termux_api(["BatteryStatus"])
            return CapabilityResult.ok(out or {"error": "termux-api unavailable"})
        if ctx.action == "android.sensors":
            out = _termux_api(["SensorList"])
            return CapabilityResult.ok(out or {"error": "termux-api sensors unavailable"})
        return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")