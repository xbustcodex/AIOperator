"""Android / TerminalP capability.

Reads device facts locally and optionally shells out to the host Android
API binary (``terminalp-api``, or compat ``termux-api``) when available for
battery, sensors, location, wifi and sms. All data collectors degrade
gracefully.
"""

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult
from buster.android_integration import termux_api
from buster.android_integration.device import device_info


class AndroidCapability(Capability):
    """Android environment introspection."""

    name = "android"
    actions_list = [
        "android.info", "android.battery", "android.sensors",
        "android.location", "android.wifi", "android.sms",
    ]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def _api_error(self, feature: str) -> str:
        api = termux_api.api_binary() or "host-api"
        return f"{api} {feature} unavailable"

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        if ctx.action == "android.info":
            return CapabilityResult.ok(device_info().__dict__)
        if ctx.action == "android.battery":
            out = termux_api.battery()
            return CapabilityResult.ok(out or {"error": self._api_error("battery")})
        if ctx.action == "android.sensors":
            out = termux_api.sensors()
            return CapabilityResult.ok(out or {"error": self._api_error("sensors")})
        if ctx.action == "android.location":
            out = termux_api.location()
            return CapabilityResult.ok(out or {"error": self._api_error("location")})
        if ctx.action == "android.wifi":
            out = termux_api.wifi()
            return CapabilityResult.ok(out or {"error": self._api_error("wifi")})
        if ctx.action == "android.sms":
            out = termux_api.sms(limit=extra.get("limit", 10))
            return CapabilityResult.ok(out or {"error": self._api_error("sms")})
        return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")