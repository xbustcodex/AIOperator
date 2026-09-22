"""Typed wrappers around the host Android API binary.

Prefers the TerminalP API binary (``terminalp-api``) and falls back to the
Termux-class ``termux-api``, both of which expose the same JSON namespaces.
Every call degrades gracefully: when neither binary is installed or a request
fails/timeouts, we return ``None`` and the caller reports the sensor or
capability as unavailable rather than raising.
"""

import json
import shutil
import subprocess
from typing import Optional

_TIMEOUT = 6.0

API_BINARIES = ("terminalp-api", "termux-api")


def api_binary() -> Optional[str]:
    """Return the detected host API binary (``terminalp-api`` preferred)."""
    for binary in API_BINARIES:
        if shutil.which(binary):
            return binary
    return None


def is_available() -> bool:
    return api_binary() is not None


def call(namespace: str, args: Optional[list[str]] = None) -> Optional[dict]:
    """Run the host API binary ``<namespace> [args]`` and parse a JSON reply."""
    binary = api_binary()
    if binary is None:
        return None
    command = [binary, namespace, *(args or [])]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return _coerce_payload(completed.stdout)


def _coerce_payload(raw: str) -> dict:
    raw = raw.strip()
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {"raw": raw}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return payload


def battery() -> Optional[dict]:
    return call("BatteryStatus")


def location() -> Optional[dict]:
    return call("Location", ["-r", "net"]) or call("Location")


def wifi() -> Optional[dict]:
    return call("WifiScanInfo")


def sms(limit: int = 10) -> Optional[list]:
    payload = call("SmsList", ["-l", str(limit)])
    if payload is None:
        return None
    items = payload.get("messages") or payload.get("value")
    return items if isinstance(items, list) else None


def sensors() -> Optional[list]:
    payload = call("SensorList")
    if payload is None:
        return None
    items = payload.get("sensors") or payload.get("value")
    return items if isinstance(items, list) else None