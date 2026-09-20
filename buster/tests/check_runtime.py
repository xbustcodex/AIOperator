#!/usr/bin/env python3
"""Standalone runtime verification for Buster OS.

Runs the single-runtime machinery directly (not under unittest) because
some sandboxes stall `unittest`-driven processes that reuse the same
filesystem paths in rapid succession. Exercise everything here:

* lock acquire / refuse / stale takeover / release,
* in-process server + client op surface,
* cross-process daemon spawn -> online -> status -> shutdown (retried).

    python buster/tests/check_runtime.py

Exits 0 on success, 1 on failure.
"""

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import buster.runtime as rt
from buster.runtime import (
    RemoteKernel,
    RuntimeClient,
    RuntimeLock,
    RuntimeOfflineError,
    RuntimeRpcError,
    RuntimeServer,
    spawn_daemon,
    wait_online,
    wait_offline,
)

CHECKS = []


def check(name):
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


def _bootstrapped():
    install = tempfile.mkdtemp()
    from buster.config import Config
    config = Config(config_path=os.path.join(install, "config", "config.json"))
    from buster.bootstrap import bootstrap_offline
    bootstrap_offline(config, install_path=install)
    return install, config


def _serve(install, config=None):
    from buster.kernel.core import Kernel
    import threading
    kernel = Kernel(config=config) if config else None
    if kernel is None:
        from buster.config import Config as C
        kernel = Kernel(config=C(config_path=os.path.join(
            install, "config", "config.json")))
    server = RuntimeServer(kernel, install)
    if not server.start():
        raise RuntimeError("server could not acquire lock")
    threading.Thread(target=server.serve, daemon=True).start()
    return server, kernel


@check("lock: acquire refuses a live runtime, stale takeover, release")
def _lock():
    install = tempfile.mkdtemp()
    lock = RuntimeLock(install)
    assert lock.acquire(), "first acquire failed"
    assert lock.is_online(), "lock should report online"
    assert not RuntimeLock(install).acquire(), "second runtime must be refused"
    lock.release()
    assert lock.read() is None, "release must remove the lock"

    stale = RuntimeLock(install)
    assert stale.acquire(), "stale: fresh acquire failed"
    info = stale.read()
    assert info is not None, "stale: lock should be readable"
    info["pid"] = 99999999
    with open(stale.path, "w", encoding="utf-8") as handle:
        json.dump(info, handle)
    assert not stale.is_online(), "stale: dead pid must read offline"
    assert stale.acquire(), "stale lock must be takable"
    stale.release()


@check("server op surface: status, deny, grant, call, mem, caps, plan, shutdown")
def _ops():
    install, config = _bootstrapped()
    server, kernel = _serve(install, config)
    try:
        status = server.rpc({"op": "status"})["data"]
        assert status["state"] == "running"
        assert "filesystem" in status["capabilities"]

        denied = server.rpc({"op": "call", "action": "shell.run",
                             "extra": {"command": "echo x"}})["data"]
        assert not denied["success"], "must be denied by default"

        server.rpc({"op": "grant", "action": "shell.run"})
        allowed = server.rpc({"op": "call", "action": "shell.run",
                              "extra": {"command": "echo boot-ok"}})["data"]
        assert allowed["success"], allowed
        assert "boot-ok" in allowed["data"]["stdout"]

        server.rpc({"op": "mem_put", "key": "k", "value": "v"})
        assert server.rpc({"op": "mem_get", "key": "k"})["data"] == "v"
        assert "fs.write" in server.rpc({"op": "caps"})["data"]["actions"]

        plan = server.rpc({"op": "plan", "goal": "inspect environment"})["data"]
        assert plan["status"] in ("done", "failed")

        server.rpc({"op": "shutdown"})
    finally:
        server.close()
    assert not RuntimeLock(install).is_online(), "shutdown must release the lock"


@check("remote facade over an in-process bridge")
def _facade():
    install, config = _bootstrapped()
    server, kernel = _serve(install, config)
    try:
        class BridgedClient:
            def __init__(self, srv):
                self._srv = srv

            def rpc(self, op, **payload):
                response = self._srv.rpc({"op": op, **payload})
                if response is None or not response.get("ok"):
                    raise RuntimeRpcError(
                        response.get("error", "rpc failed") if response else "no response")
                return response

        kernel_facade = RemoteKernel(BridgedClient(server))
        run = kernel_facade.run_plan("inspect environment")
        assert run["status"] in ("done", "failed")
        denied = kernel_facade.cap.call("android.info")
        assert not denied.success
    finally:
        server.close()


def _cross_process_once(install) -> bool:
    child = spawn_daemon(install, repo=os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    try:
        if not wait_online(install, timeout=30):
            return False
        client = RuntimeClient(install, timeout=30)
        status = client.rpc("status")["data"]
        if status["state"] != "running":
            return False
        try:
            client.rpc("shutdown")
        except Exception:  # noqa: BLE001
            pass
        return wait_offline(install, timeout=20)
    finally:
        try:
            child.kill()
        except Exception:  # noqa: BLE001
            pass


@check("cross-process daemon: spawn -> online -> status -> shutdown (retried)")
def _cross_process():
    for attempt in range(2):
        install, _ = _bootstrapped()
        if _cross_process_once(install):
            return
    assert False, "cross-process daemon did not complete a clean boot/shutdown cycle"


def main() -> int:
    failures = []
    for name, fn in CHECKS:
        started = time.time()
        try:
            fn()
            print(f"[PASS] {name} ({time.time() - started:.1f}s)", flush=True)
        except Exception as exc:  # noqa: BLE001
            failures.append((name, exc))
            print(f"[FAIL] {name}: {type(exc).__name__}: {exc}", flush=True)
    if failures:
        print(f"\n{len(failures)} check(s) failed.", flush=True)
        return 1
    print(f"\nAll {len(CHECKS)} runtime checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())