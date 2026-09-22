"""Time utilities capability."""

import datetime
import time

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


class TimeCapability(Capability):
    """``time.now``, ``time.format``, ``time.sleep``."""

    name = "time"
    actions_list = ["time.now", "time.format", "time.sleep"]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        if ctx.action == "time.now":
            now = datetime.datetime.now()
            return CapabilityResult.ok({
                "iso": now.isoformat(timespec="seconds"),
                "unix": int(time.time()),
                "utc": datetime.datetime.utcnow().isoformat(timespec="seconds"),
            })
        if ctx.action == "time.format":
            fmt = extra.get("format", "%Y-%m-%d %H:%M:%S")
            return CapabilityResult.ok(datetime.datetime.now().strftime(fmt))
        if ctx.action == "time.sleep":
            seconds = float(extra.get("seconds", 0))
            if seconds < 0 or seconds > 3600:
                return CapabilityResult.fail("sleep outside allowed range (0..3600s)")
            time.sleep(seconds)
            return CapabilityResult.ok({"slept_seconds": seconds})
        return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")