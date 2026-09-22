"""TerminalP (host) / Android device detection and device facts.

TerminalP is the first-class phone host for Buster OS. Termux-class
environments remain recognized for compatibility: any Android terminal whose
``$PREFIX`` points at an app-local ``/files/usr`` tree (or that sets a
TerminalP / Termux marker) is a valid host.
"""

import os
import subprocess
from dataclasses import dataclass

PREFIX = os.environ.get("PREFIX", "")

#: Path/env markers that identify TerminalP as the host.
_TERMINALP_MARKERS = ("terminalp", "com.prime.tech", "prime.tech", "prime-tech")


def _looks_like_android_terminal() -> bool:
    return PREFIX.startswith("/data/data/") and "/files/usr" in PREFIX


def host_identity() -> str:
    """Return ``terminalp``, ``termux``, ``android-terminal`` or ``desktop``."""
    lowered = PREFIX.lower()
    if os.environ.get("TERMINALP_VERSION") is not None or \
            any(marker in lowered for marker in _TERMINALP_MARKERS):
        return "terminalp"
    if "termux" in lowered or os.environ.get("TERMUX_VERSION") is not None:
        return "termux"
    if _looks_like_android_terminal():
        return "android-terminal"
    return "desktop"


def is_termux_compatible() -> bool:
    """True when running inside TerminalP or another Termux-class host."""
    return host_identity() in ("terminalp", "termux", "android-terminal")


def is_terminalp() -> bool:
    """True when running inside TerminalP specifically."""
    return host_identity() == "terminalp"


def is_termux() -> bool:
    """True when running inside Termux specifically (compat helper)."""
    return host_identity() == "termux"


def android_prop(name: str) -> str:
    """Read an Android system property via ``getprop``, '' on failure."""
    if not is_termux_compatible():
        return ""
    try:
        completed = subprocess.run(
            ["getprop", name], capture_output=True, text=True, timeout=3,
        )
        if completed.returncode == 0:
            return completed.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


@dataclass
class DeviceInfo:
    prefix: str
    host: str
    phone_host: bool
    terminalp: bool
    is_aarch64: bool
    uname: str
    android_release: str = ""
    android_sdk: str = ""
    model: str = ""
    termux: bool = False  # compatibility field


def device_info() -> DeviceInfo:
    import platform

    return DeviceInfo(
        prefix=PREFIX,
        host=host_identity(),
        phone_host=is_termux_compatible(),
        terminalp=is_terminalp(),
        termux=is_termux(),
        is_aarch64=platform.machine().lower() in ("aarch64", "arm64"),
        uname=" ".join(platform.uname()),
        android_release=android_prop("ro.build.version.release"),
        android_sdk=android_prop("ro.build.version.sdk"),
        model=android_prop("ro.product.model"),
    )