"""Android / TerminalP integration for Buster OS."""

from buster.android_integration import termux_api
from buster.android_integration.device import (
    DeviceInfo,
    android_prop,
    device_info,
    host_identity,
    is_terminalp,
    is_termux,
    is_termux_compatible,
)
from buster.android_integration.termux_api import api_binary

__all__ = [
    "DeviceInfo",
    "android_prop",
    "api_binary",
    "device_info",
    "host_identity",
    "is_terminalp",
    "is_termux",
    "is_termux_compatible",
    "termux_api",
]