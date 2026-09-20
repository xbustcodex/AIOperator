"""Termux / Android device detection and device facts."""

import os
from dataclasses import dataclass

PREFIX = os.environ.get("PREFIX", "")


def is_termux() -> bool:
    """Detect whether we are running inside Termux."""
    return "termux" in PREFIX.lower() or os.environ.get("TERMUX_VERSION") is not None


@dataclass
class DeviceInfo:
    prefix: str
    termux: bool
    is_aarch64: bool
    uname: str


def device_info() -> DeviceInfo:
    import platform

    return DeviceInfo(
        prefix=PREFIX,
        termux=is_termux(),
        is_aarch64=platform.machine().lower() in ("aarch64", "arm64"),
        uname=" ".join(platform.uname()),
    )