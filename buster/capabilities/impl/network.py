"""Networking capability (stdlib-only HTTP client)."""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


class NetworkCapability(Capability):
    """HTTP GET/POST and network resolution through the standard library."""

    name = "network"
    actions_list = ["net.get", "net.post", "net.dns", "net.ping"]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        if ctx.action == "net.get":
            return CapabilityResult.ok(self._request(extra.get("url"), "GET"))
        if ctx.action == "net.post":
            if extra.get("json") is not None:
                body = json.dumps(extra["json"]).encode("utf-8")
            else:
                body = html_to_form(extra.get("data"))
            return CapabilityResult.ok(self._request(extra.get("url"), "POST", body=body))
        if ctx.action == "net.dns":
            try:
                import socket
                info = socket.getaddrinfo(extra.get("host"), extra.get("port", 0))
                return CapabilityResult.ok({"host": extra.get("host"), "results": info})
            except Exception as exc:  # noqa: BLE001
                return CapabilityResult.fail(f"socket: {exc}")
        if ctx.action == "net.ping":
            import subprocess
            try:
                completed = subprocess.run(
                    ["ping", "-c", str(extra.get("count", 3)), extra.get("host", "localhost")],
                    capture_output=True, text=True, timeout=extra.get("timeout", 10),
                )
                return CapabilityResult.ok({
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout,
                })
            except Exception as exc:  # noqa: BLE001
                return CapabilityResult.fail(f"ping: {exc}")
        return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")

    @staticmethod
    def _request(url: Optional[str], method: str, body: Optional[bytes] = None) -> dict:
        if not url:
            return {"error": "Missing 'url'"}
        request = urllib.request.Request(url=url, method=method, data=body)
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw)
                except ValueError:
                    payload = raw
                return {"status": response.status, "headers": dict(response.headers), "body": payload}
        except urllib.error.HTTPError as exc:
            return {"error": f"HTTP {exc.code}", "status": exc.code}
        except urllib.error.URLError as exc:
            return {"error": str(exc.reason)}


def html_to_form(data: Optional[dict]) -> Optional[bytes]:
    if data is None:
        return None
    return urllib.parse.urlencode(data).encode("utf-8")