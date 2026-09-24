"""Buster OS GUI — local web frontend server.

Pure client of the Buster daemon. Every command and state read goes over the
existing file-based RuntimeClient/RemoteKernel to the live runtime; the GUI
process never instantiates a Kernel, EventRouter, Scheduler, memory authority
or agent system. The daemon continues independently of this UI.
"""

import json
import logging
import os
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from buster.runtime import RemoteKernel, RuntimeClient, RuntimeOfflineError, RuntimeRpcError
from buster.version import get_version

GUI_VERSION = get_version()
DEFAULT_PORT = 8468

log = logging.getLogger("buster.gui")


class GuiOfflineError(Exception):
    """Raised when the Buster runtime is not reachable."""


class _Handler(BaseHTTPRequestHandler):
    server_version = "BusterOS-GUI"

    # -- dispatch -------------------------------------------------------

    def do_GET(self):  # noqa: N802
        self._dispatch()

    def do_POST(self):  # noqa: N802
        self._dispatch()

    def do_DELETE(self):  # noqa: N802
        self._dispatch()

    def _dispatch(self):
        gui = getattr(self.server, "gui", None)
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            body_length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(body_length) if body_length else b""
            payload = json.loads(body.decode("utf-8")) if body else {}
        except ValueError:
            payload = {}
        try:
            gui.route(self, self.command, path, query, payload)
        except Exception as exc:  # noqa: BLE001
            log.exception("route %s %s failed", self.command, path)
            self.send_json(500, {"error": f"internal GUI error: {exc}"})

    # -- helpers ---------------------------------------------------------

    def send_json(self, code: int, data) -> None:
        raw = json.dumps(data, default=str)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw.encode("utf-8"))))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw.encode("utf-8"))

    def send_static(self, rel: str) -> None:
        gui = getattr(self.server, "gui", None)
        path = os.path.normpath(os.path.join(gui.web_dir, rel.lstrip("/")))
        if not path.startswith(os.path.abspath(gui.web_dir)):
            self.send_json(403, {"error": "forbidden"})
            return
        if not os.path.isfile(path):
            self.send_json(404, {"error": "not found"})
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".mjs": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".json": "application/json",
            ".png": "image/png",
            ".ico": "image/x-icon",
        }.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        with open(path, "rb") as handle:
            raw = handle.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def log_message(self, fmt, *args):  # noqa: A003
        if False:  # keep quiet unless debugging
            super().log_message(fmt, *args)


class GuiServer:
    """Serves the consumer UI and JSON API against one Buster runtime."""

    def __init__(self, install_path: str, host: str = "127.0.0.1",
                 port: int = DEFAULT_PORT, web_dir: str | None = None):
        self.install_path = install_path
        self.host = host
        self.port = port
        here = os.path.dirname(os.path.abspath(__file__))
        self.web_dir = web_dir or os.path.join(here, "web")
        self.client = RuntimeClient(install_path, timeout=8.0)
        self.daemon = RemoteKernel(self.client)
        self.httpd = ThreadingHTTPServer((host, port), _Handler)
        self.httpd.daemon_threads = True
        self.httpd.gui = self
        self.port = self.httpd.server_address[1]
        self._serving = False

    # -- lifecycle -------------------------------------------------------

    def serve_forever(self):
        self._serving = True
        log.info("Buster GUI listening on http://%s:%s (runtime %s)",
                 self.host, self.port, self.install_path)
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.httpd.server_close()

    def stop(self):
        if self._serving:
            self.httpd.shutdown()
        else:
            self.httpd.server_close()

    # -- RPC guard -------------------------------------------------------

    def _rpc(self, fn, fallback=None):
        try:
            return fn()
        except (RuntimeOfflineError, RuntimeRpcError) as exc:
            raise GuiOfflineError(str(exc)) from exc

    # -- HTTP routing ------------------------------------------------------

    def route(self, handler, method: str, path: str, query: dict,
              payload: dict) -> None:
        if path == "/" or path.startswith("/assets/"):
            rel = "index.html" if path == "/" else path.lstrip("/")
            handler.send_static(rel)
            return
        try:
            self._api_route(handler, method, path, query, payload)
        except GuiOfflineError as exc:
            handler.send_json(503, {"offline": True,
                                    "error": "Buster runtime is offline",
                                    "detail": str(exc)})

    def _api_route(self, handler, method, path, query, payload):
        if path == "/api/ping":
            return handler.send_json(200, {"ok": True, "gui": "buster-gui",
                                           "version": GUI_VERSION})
        if path == "/api/bootstrap":
            info = self._rpc(lambda: self.daemon.update_info())
            status = self._rpc(lambda: self.daemon.status())
            host = "unknown"
            try:
                host = (self.daemon.intel_view("world") or {}).get("facts", {}).get("host", "unknown")
            except Exception:  # noqa: BLE001
                pass
            return handler.send_json(200, {
                "buster_version": info.get("buster_version", GUI_VERSION),
                "install_path": info.get("install_path", self.install_path),
                "runtime_state": status.get("state"),
                "online": True,
                "host": host,
            })

        if path == "/api/home":
            status = self._rpc(lambda: self.daemon.status())
            health = self.daemon.intel_view("health")
            activity = self._rpc(lambda: self.daemon.activity())
            return handler.send_json(200, {
                "status": {k: status.get(k) for k in
                           ("state", "event_router_running", "scheduler_running",
                            "ai_providers", "capabilities")},
                "health": health,
                "activity": activity,
            })

        if path == "/api/activity":
            return handler.send_json(200, self._rpc(lambda: self.daemon.activity()))

        if path == "/api/chat" and method == "POST":
            return handler.send_json(200, self._chat(payload))
        if path == "/api/chat" and method == "GET":
            session = (query.get("session") or ["default"])[0]
            history = self.daemon.memory.store.get(f"chat:{session}", default=[])
            return handler.send_json(200, {"session": session, "history": history})
        if (path, method) == ("/api/chat", "DELETE"):
            session = (query.get("session") or ["default"])[0]
            self.daemon.memory.store.put(f"chat:{session}", [])
            return handler.send_json(200, {"cleared": session})

        if path == "/api/files":
            folder = (query.get("path") or ["."])[0]
            result = self.daemon.cap.call("fs.list", extra={"path": folder})
            if not result.success:
                return handler.send_json(200, {"ok": False, "error": result.error})
            return handler.send_json(200, {"ok": True, "data": result.data,
                                           "actor": "gui"})
        if path == "/api/file":
            file_path = (query.get("path") or [""])[0]
            result = self.daemon.cap.call("fs.read", extra={"path": file_path})
            return handler.send_json(200, {"ok": result.success,
                                           "data": result.data,
                                           "error": result.error})
        if path == "/api/fs":
            result = self.daemon.cap.call(payload.get("action", ""),
                                          extra=payload.get("params") or {},
                                          context={"actor": "gui", "source": "gui"})
            return handler.send_json(200, {"ok": result.success,
                                           "data": result.data,
                                           "error": result.error})

        if path == "/api/device":
            return handler.send_json(200, self._rpc(
                lambda: self.daemon.perception.snapshot()))

        if path == "/api/goals" and method == "GET":
            view = self.daemon.intel_view("goals")
            return handler.send_json(200, view)
        if path == "/api/goals" and method == "POST":
            goal = self.daemon.create_goal(payload.get("text", ""),
                                           kind=payload.get("kind", "task"))
            return handler.send_json(200, {"goal": goal, "created": True})
        if path == "/api/goals/run":
            result = self._rpc(lambda: self.daemon.process_goal(
                payload.get("text", ""), tentative=bool(payload.get("tentative", False))))
            return handler.send_json(200, result)

        if path == "/api/memory":
            view = self.daemon.intel_view("memory")
            keys = self.daemon.memory.store.keys()
            prefs = {}
            for key in keys:
                if str(key).startswith("pref:"):
                    prefs[str(key)[5:]] = self.daemon.memory.store.get(key)
            return handler.send_json(200, {"stats": view, "preferences": prefs})
        if path == "/api/prefs":
            key = payload.get("key", "")
            self.daemon.memory.store.put(f"pref:{key}", payload.get("value", ""))
            return handler.send_json(200, {"saved": key})

        if path == "/api/permissions" and method == "GET":
            return handler.send_json(200, self._rpc(
                lambda: self.daemon.permissions_list()))
        if path == "/api/permissions/grant":
            action = payload.get("action", "")
            self.daemon.permissions.grant(action)
            return handler.send_json(200, {"granted": action})
        if path == "/api/permissions/deny":
            action = payload.get("action", "")
            self.daemon.permissions.deny(action)
            return handler.send_json(200, {"denied": action})

        if path == "/api/attention":
            activity = self._rpc(lambda: self.daemon.activity())
            health = self.daemon.intel_view("health")
            upgrade = {
                "suggestions": activity.get("suggestions", []),
                "active_goals": [g for g in activity.get("goals", [])
                                 if g.get("status") == "active"],
                "recent_events": activity.get("events", [])[-10:],
                "health": health,
            }
            return handler.send_json(200, upgrade)

        if path == "/api/advanced":
            section = "health"
        elif path.startswith("/api/advanced/"):
            section = path.split("/api/advanced/", 1)[1]
        else:
            section = None
        if section is not None:
            view = self._advanced_view(section)
            return handler.send_json(200, view)

        if path == "/api/settings":
            return handler.send_json(200, {
                "status": self._rpc(lambda: self.daemon.status()),
                "permissions": self._rpc(lambda: self.daemon.permissions_list()),
                "updates": self._rpc(lambda: self.daemon.update_info()),
            })

        if path == "/api/updates":
            return handler.send_json(200, self._rpc(
                lambda: self.daemon.update_info()))

        handler.send_json(404, {"error": f"unknown endpoint {path}"})

    # -- advanced mapping -------------------------------------------------

    def _advanced_view(self, section: str) -> dict:
        """Map a technical Advanced section to the real runtime client ops."""
        try:
            if section in ("health", "providers", "memory", "goals", "world",
                           "curiosity", "attention", "rhythm", "nervous", "plans"):
                return self._rpc(lambda: self.daemon.intel_view(section))
            if section == "status":
                return self._rpc(lambda: self.daemon.status())
            if section == "capabilities":
                return self._rpc(lambda: {
                    "capabilities": self.daemon.cap.list_capabilities(),
                    "actions": self.daemon.cap.list_actions(),
                })
            if section == "jobs":
                jobs = self._rpc(lambda: self.daemon.scheduler.list_jobs())
                return {"jobs": [{"id": j.id, "name": j.name,
                                  "status": j.status.value,
                                  "periodic": j.periodic} for j in jobs]}
            if section == "audit":
                entries = self._rpc(lambda: self.daemon.audit.tail(limit=30))
                return {"audit": entries}
            if section == "permissions":
                return self._rpc(lambda: self.daemon.permissions_list())
            if section == "activity":
                return self._rpc(lambda: self.daemon.activity())
            return self._rpc(lambda: self.daemon.intel_view(section))
        except GuiOfflineError:
            return {"offline": True}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def _chat(self, payload: dict) -> dict:
        message = (payload.get("message") or "").strip()
        session = payload.get("session") or "default"
        if not message:
            return {"error": "empty message"}
        key = f"chat:{session}"
        history = self.daemon.memory.store.get(key, default=[])
        if not isinstance(history, list):
            history = []
        history.append({"role": "user", "text": message, "ts": time.time()})

        result = self._rpc(lambda: self.daemon.process_goal(message,
                                                            tentative=False))
        reply = _summarize_result(message, result)
        history.append({"role": "buster", "text": reply, "ts": time.time(),
                        "meta": result})
        self.daemon.memory.store.put(key, history)
        return {"session": session, "reply": reply, "result": result,
                "history": history}


def _summarize_result(message: str, result: dict) -> str:
    status = result.get("status", "unknown")
    if status == "done":
        return (f"I handled that — {message!r} is done "
                f"({result.get('steps', 0)} step(s)).")
    if status == "failed":
        detail = result.get("error") or "it ran into a problem"
        return f"I couldn't finish that one: {detail}."
    return f"I've noted that ({status}); it's queued in my work."


def run_gui(install_path: str, host: str = "127.0.0.1",
            port: int = DEFAULT_PORT) -> GuiServer:
    server = GuiServer(install_path, host=host, port=port)
    server.serve_forever()
    return server