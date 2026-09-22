"""Single-runtime lifecycle for Buster OS.

Owns the invariant that there is **exactly one Kernel instance** per
install. A ``RuntimeLock`` file prevents competing runtimes: the daemon
acquires it atomically on ``start`` and releases it on ``stop``. ``status``
and ``shell`` are read-only clients that never instantiate a Kernel of
their own.

Transport
    The daemon and clients exchange JSON request/response files under
    ``install/state/rpc/``. This channel is deterministic on every OS
    (Windows dev host and TerminalP/Linux alike) and imposes no scheduler or
    kernel load while idle.

Layout
    install/state/runtime.lock          PID + RPC identity of the live runtime
    install/state/runtime.status.json   Heartbeat snapshot by the daemon
    install/state/rpc/in/<id>.json      Client requests
    install/state/rpc/out/<id>.json     Daemon responses

The daemon serves the RPC surface regardless of transport: call, status,
caps, grant, deny, jobs, jobs_cancel, run_async, mem_*, audit, sensors,
plan, shutdown.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from typing import Optional

LOCK_NAME = "runtime.lock"
HEARTBEAT_NAME = "runtime.status.json"
RPC_DIR = "rpc"
REQUEST_TTL = 60.0  # seconds; stale request files are swept


def state_dir(install_path: str) -> str:
    return os.path.join(install_path, "state")


def _rpc_dirs(install_path: str) -> tuple:
    base = os.path.join(state_dir(install_path), RPC_DIR)
    in_dir = os.path.join(base, "in")
    out_dir = os.path.join(base, "out")
    os.makedirs(in_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    return in_dir, out_dir


def _pid_alive(pid: Optional[int]) -> bool:
    if pid is None:
        return False
    try:
        if os.name == "nt":
            return _pid_alive_windows(pid)
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # owned by another user and alive
    except OSError:
        return False


def _pid_alive_windows(pid: int) -> bool:
    """Probe process liveness without signals.

    ``os.kill(pid, 0)`` can hang on some Windows Python builds (store /
    EDR-instrumented), so we use OpenProcess directly.
    """
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    except Exception:  # noqa: BLE001 - never block the runtime on a probe
        return True


def _serialize(value):
    """Best-effort JSON encoding for RPC payloads."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return str(value)


def _atomic_write(path: str, payload: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, default=str)
    os.replace(tmp, path)


def _read_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


class RuntimeLock:
    """Atomic, PID-aware lock guaranteeing a single live runtime."""

    def __init__(self, install_path: str):
        self.path = os.path.join(state_dir(install_path), LOCK_NAME)

    def acquire(self) -> bool:
        """Acquire the lock, refusing while another live runtime holds it."""
        parent = os.path.dirname(self.path)
        if not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        payload = json.dumps({"pid": os.getpid(), "at": time.time()})
        fd = None
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                break
            except FileExistsError:
                current = _read_json(self.path)
                if current and _pid_alive(current.get("pid")):
                    return False
                try:
                    os.remove(self.path)
                except OSError:
                    pass
                except FileNotFoundError:
                    pass
        if fd is None:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        return True

    def release(self) -> None:
        try:
            os.remove(self.path)
        except OSError:
            pass

    def read(self) -> Optional[dict]:
        return _read_json(self.path)

    def is_online(self) -> bool:
        current = self.read()
        return bool(current and _pid_alive(current.get("pid")))


class RuntimeServer:
    """Daemon-side processor owning exactly one kernel."""

    POLL_INTERVAL = 0.1

    def __init__(self, kernel, install_path: str):
        self.kernel = kernel
        self.install_path = install_path
        self.lock = RuntimeLock(install_path)
        self.in_dir, self.out_dir = _rpc_dirs(install_path)
        self._running = True
        self._processed = set()
        self.logger = logging.getLogger("buster.runtime.server")

    # -- lifecycle ---------------------------------------------------

    def start(self) -> bool:
        if not self.lock.acquire():
            return False
        self.kernel.runtime_lock = self.lock
        self.kernel.start()
        self._heartbeat()
        self._arm_heartbeat_job()
        self.logger.info("Runtime online (pid %s)", os.getpid())
        return True

    def serve(self) -> None:
        while self._running:
            self._process_pending()
            time.sleep(self.POLL_INTERVAL)
        self.logger.info("Runtime serve loop exited.")

    def shutdown(self) -> None:
        self._running = False

    def close(self) -> None:
        self.kernel.stop()
        self.lock.release()
        self.logger.info("Runtime offline.")

    # -- request processing ------------------------------------------

    def _process_pending(self) -> None:
        try:
            names = os.listdir(self.in_dir)
        except OSError:
            return
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(self.in_dir, name)
            request = _read_json(path)
            if request is None:
                # Broken/stale request: sweep when too old.
                if _mtime_older_than(path, REQUEST_TTL):
                    self._safe_remove(path)
                continue
            self._dispatch(request, path)

    def _dispatch(self, request: dict, source: str) -> None:
        request_id = request.get("id")
        try:
            response = self.rpc(request)
        except Exception as exc:  # noqa: BLE001
            response = {"op": request.get("op"), "ok": False,
                        "error": f"{type(exc).__name__}: {exc}"}
        if request_id:
            _atomic_write(os.path.join(self.out_dir, f"{request_id}.json"),
                          {**response, "reply_to": request_id})
        self._safe_remove(source)

    # -- RPC surface --------------------------------------------------

    def rpc(self, message: dict) -> Optional[dict]:
        op = message.get("op")
        try:
            if op == "call":
                result = self.kernel.cap.call(
                    message.get("action"),
                    extra=message.get("extra"),
                    context=message.get("context"),
                )
                return {"op": op, "ok": True, "data": {
                    "success": result.success, "data": _serialize(result.data),
                    "error": result.error,
                }}
            if op == "run_async":
                job = self.kernel.cap.run_async(
                    message.get("action"),
                    extra=message.get("extra"),
                    context=message.get("context"),
                )
                return {"op": op, "ok": True, "data": _serialize({
                    "id": job.id, "name": job.name,
                })}
            if op == "status":
                status = self.kernel.status()
                status["memory"] = self.kernel.memory.snapshot()
                return {"op": op, "ok": True, "data": _serialize(status)}
            if op == "caps":
                return {"op": op, "ok": True, "data": {
                    "capabilities": self.kernel.cap.list_capabilities(),
                    "actions": self.kernel.cap.list_actions(),
                }}
            if op == "grant":
                self.kernel.permissions.grant(message.get("action"),
                                              note="granted over runtime")
                return {"op": op, "ok": True, "data": message.get("action")}
            if op == "deny":
                self.kernel.permissions.deny(message.get("action"),
                                             note="denied over runtime")
                return {"op": op, "ok": True, "data": message.get("action")}
            if op == "jobs":
                jobs = [{"id": j.id, "name": j.name, "status": j.status.value,
                         "periodic": bool(j.periodic)} for j in
                        self.kernel.scheduler.list_jobs()]
                return {"op": op, "ok": True, "data": jobs}
            if op == "jobs_cancel":
                cancelled = self.kernel.scheduler.cancel(message.get("id", ""))
                return {"op": op, "ok": cancelled, "data": message.get("id"),
                        "error": None if cancelled else "no pending job"}
            if op == "mem_put":
                self.kernel.memory.store.put(message.get("key"),
                                             message.get("value"))
                return {"op": op, "ok": True, "data": message.get("key")}
            if op == "mem_get":
                return {"op": op, "ok": True,
                        "data": self.kernel.memory.store.get(message.get("key"))}
            if op == "mem_keys":
                return {"op": op, "ok": True,
                        "data": self.kernel.memory.store.keys()}
            if op == "audit":
                entries = self.kernel.audit.tail(limit=message.get("limit", 10))
                return {"op": op, "ok": True, "data": _serialize(entries)}
            if op == "sensors":
                return {"op": op, "ok": True,
                        "data": _serialize(self.kernel.perception.snapshot())}
            if op == "plan":
                from buster.agents.orchestration import AgentOrchestrator
                run = AgentOrchestrator(kernel=self.kernel).run(
                    message.get("goal", ""))
                return {"op": op, "ok": True, "data": _serialize({
                    "status": run.status.value, "error": run.error,
                    "result": run.result, "steps": len(run.history),
                })}
            if op == "shutdown":
                self._running = False
                self.logger.info("Shutdown requested.")
                return {"op": op, "ok": True, "data": "stopping"}
            self.logger.warning("Unknown RPC op '%s'", op)
            return {"op": op, "ok": False, "error": f"unknown op '{op}'"}
        except Exception as exc:  # noqa: BLE001 - never leak broken requests
            self.logger.exception("RPC '%s' failed", op)
            return {"op": op, "ok": False, "error": f"{type(exc).__name__}: {exc}"}

    # -- heartbeat ---------------------------------------------------

    def _heartbeat(self) -> None:
        snapshot = self.kernel.status()
        snapshot["pid"] = os.getpid()
        snapshot["ts"] = time.time()
        try:
            _atomic_write(os.path.join(state_dir(self.install_path), HEARTBEAT_NAME),
                          snapshot)
        except OSError:
            self.logger.exception("Heartbeat write failed")

    def _arm_heartbeat_job(self) -> None:
        self.kernel.scheduler.schedule("runtime.heartbeat",
                                       lambda job: self._heartbeat(),
                                       every=2.0)

    @staticmethod
    def _safe_remove(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass


class RuntimeClient:
    """Read-only client for status/shell/stop against the live runtime."""

    def __init__(self, install_path: str, timeout: float = 10.0):
        self.install_path = install_path
        self.lock = RuntimeLock(install_path)
        self.timeout = timeout

    def is_online(self) -> bool:
        return self.lock.is_online()

    def rpc(self, op: str, **payload) -> dict:
        info = self.lock.read()
        if not info or not _pid_alive(info.get("pid")):
            raise RuntimeOfflineError("No Buster runtime is online")

        request_id = uuid.uuid4().hex
        in_dir, out_dir = _rpc_dirs(self.install_path)
        request = {"op": op, "id": request_id, **payload}
        _atomic_write(os.path.join(in_dir, f"{request_id}.json"), request)

        response_path = os.path.join(out_dir, f"{request_id}.json")
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            response = _read_json(response_path)
            if response is not None:
                self._safe_remove(response_path)
                if not response.get("ok"):
                    raise RuntimeRpcError(response.get("error", "rpc failed"))
                return response
            time.sleep(0.02)

        self._safe_remove(response_path)
        # The daemon will sweep the request once it is stale.
        raise RuntimeRpcError(f"RPC '{op}' timed out after {self.timeout:.1f}s")

    @staticmethod
    def _safe_remove(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass


class RuntimeOfflineError(Exception):
    pass


class RuntimeRpcError(Exception):
    pass


# --------------------------------------------------------------------------
# Remote kernel facade — a minimal read-only mirror used by the RPC shell.
# --------------------------------------------------------------------------


class RemoteKernel:
    """Drives a live daemon kernel over RPC without a local Kernel."""

    def __init__(self, client: RuntimeClient):
        self.rpc = client.rpc
        self.cap = RemoteCapability(self)
        self.scheduler = RemoteScheduler(self)
        self.memory = RemoteMemory(self)
        self.audit = RemoteAudit(self)
        self.permissions = RemotePermissions(self)
        self.perception = RemotePerception(self)

    def status(self) -> dict:
        return self.rpc("status")["data"]

    def run_plan(self, goal: str) -> dict:
        return self.rpc("plan", goal=goal)["data"]


class RemoteCapability:
    def __init__(self, kernel: RemoteKernel):
        self._kernel = kernel

    def call(self, action, scope=None, extra=None, context=None) -> object:
        response = self._kernel.rpc("call", action=action, extra=extra,
                                    context=context)["data"]
        return _RemoteResult(**response)

    def run_async(self, action, scope=None, extra=None, context=None):
        data = self._kernel.rpc("run_async", action=action, extra=extra,
                                context=context)["data"]
        return _RemoteJob({"id": data["id"], "name": data["name"],
                           "status": "pending", "periodic": False})

    def list_capabilities(self) -> list:
        return self._kernel.rpc("caps")["data"]["capabilities"]

    def list_actions(self) -> list:
        return self._kernel.rpc("caps")["data"]["actions"]


class _RemoteResult:
    def __init__(self, success, data=None, error=None):
        self.success = success
        self.data = data
        self.error = error


class RemoteScheduler:
    def __init__(self, kernel: RemoteKernel):
        self._kernel = kernel

    def list_jobs(self):
        rows = self._kernel.rpc("jobs")["data"]
        return [_RemoteJob(row) for row in rows]

    def cancel(self, job_id: str) -> bool:
        response = self._kernel.rpc("jobs_cancel", id=job_id)
        return bool(response.get("data")) if response.get("ok") else False


class _RemoteJob:
    def __init__(self, row: dict):
        self.id = row["id"]
        self.name = row["name"]
        self.status = _Status(row.get("status", "pending"))
        self.periodic = bool(row.get("periodic", False))


class _Status:
    def __init__(self, value: str):
        self.value = value


class RemoteMemory:
    def __init__(self, kernel: RemoteKernel):
        self._kernel = kernel
        self.store = RemoteStore(kernel)


class RemoteStore:
    def __init__(self, kernel: RemoteKernel):
        self._kernel = kernel

    def get(self, key, default=None):
        try:
            return self._kernel.rpc("mem_get", key=key)["data"]
        except (RuntimeOfflineError, RuntimeRpcError):
            return default

    def put(self, key, value) -> None:
        self._kernel.rpc("mem_put", key=key, value=value)

    def keys(self):
        return self._kernel.rpc("mem_keys")["data"]


class RemoteAudit:
    def __init__(self, kernel: RemoteKernel):
        self._kernel = kernel

    def tail(self, limit: int = 20):
        return self._kernel.rpc("audit", limit=limit)["data"]


class RemotePermissions:
    def __init__(self, kernel: RemoteKernel):
        self._kernel = kernel

    def grant(self, action, scope=None, note=""):
        self._kernel.rpc("grant", action=action)

    def deny(self, action, scope=None, note=""):
        self._kernel.rpc("deny", action=action)


class RemotePerception:
    def __init__(self, kernel: RemoteKernel):
        self._kernel = kernel

    def snapshot(self):
        return self._kernel.rpc("sensors")["data"]


# --------------------------------------------------------------------------
# Daemon process entry
# --------------------------------------------------------------------------


def run_daemon(install_path: str, config=None) -> int:
    from buster.config import Config
    from buster.kernel.core import Kernel

    config = config or Config(config_path=os.path.join(
        install_path, "config", "config.json"))

    kernel = Kernel(config=config)
    server = RuntimeServer(kernel, install_path)
    if not server.start():
        print("Runtime already online; refusing to start a second instance.",
              file=sys.stderr)
        return 3

    from buster.bootstrap import seed_runtime
    seed_runtime(kernel)

    try:
        server.serve()
    finally:
        server.close()
    return 0


def spawn_daemon(install_path: str, python: Optional[str] = None,
                 repo: Optional[str] = None) -> subprocess.Popen:
    """Detach a background runtime daemon process. Returns the child Popen."""
    env = dict(os.environ)
    repo = repo or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = (repo + (os.pathsep if env.get("PYTHONPATH") else "") +
                         (env.get("PYTHONPATH", "")))
    child = subprocess.Popen(
        [_python_bin(python), "-m", "buster.cli", "daemon",
         "--install-path", install_path],
        env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
    )
    return child


def _python_bin(python: Optional[str]) -> str:
    return python or sys.executable


def wait_online(install_path: str, timeout: float = 15.0) -> bool:
    client = RuntimeClient(install_path, timeout=3.0)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            client.rpc("status")
            return True
        except (RuntimeOfflineError, RuntimeRpcError):
            time.sleep(0.1)
    return False


def wait_offline(install_path: str, timeout: float = 10.0) -> bool:
    client = RuntimeClient(install_path, timeout=3.0)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not client.lock.is_online():
            return True
        time.sleep(0.1)
    return False


def _mtime_older_than(path: str, seconds: float) -> bool:
    try:
        return time.time() - os.path.getmtime(path) > seconds
    except OSError:
        return False