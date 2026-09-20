"""Deterministic unit-style tests for the single-runtime lifecycle.

The comprehensive runtime verification (lock semantics, full op surface,
cross-process daemon boot) lives in ``buster/tests/check_runtime.py`` which
runs standalone and is exercised by the build. These unittest cases cover
the RPC op surface and lock refusal on a shared in-process runtime only.

Run the build (or ``python buster/tests/check_runtime.py``) for end-to-end
runtime validation.
"""

import os
import tempfile
import unittest

from buster.runtime import (
    RuntimeClient,
    RuntimeLock,
    RuntimeOfflineError,
    RuntimeRpcError,
    RemoteKernel,
    RuntimeServer,
)


def _bootstrapped_install() -> tuple:
    install = tempfile.mkdtemp()
    from buster.config import Config
    config = Config(config_path=os.path.join(install, "config", "config.json"))
    from buster.bootstrap import bootstrap_offline
    bootstrap_offline(config, install_path=install)
    return install, config


def _inprocess_server(install, config=None):
    import threading
    from buster.kernel.core import Kernel
    kernel = Kernel(config=config) if config else None
    if kernel is None:
        from buster.config import Config as C
        kernel = Kernel(config=C(config_path=os.path.join(
            install, "config", "config.json")))
    server = RuntimeServer(kernel, install)
    if not server.start():
        raise RuntimeError("in-process server could not acquire lock")
    threading.Thread(target=server.serve, daemon=True).start()
    return server, kernel


class InProcessRuntimeTests(unittest.TestCase):
    """RPC op surface against one live (in-process) runtime."""

    @classmethod
    def setUpClass(cls):
        cls.install, cls.config = _bootstrapped_install()
        cls.server, cls.kernel = _inprocess_server(cls.install, cls.config)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.close()
        except Exception:  # noqa: BLE001
            pass

    def _rpc(self, op, **payload) -> dict:
        response = self.server.rpc({"op": op, **payload})
        self.assertIsNotNone(response)
        return response

    def test_status_and_memory_snapshot(self):
        status = self._rpc("status")["data"]
        self.assertEqual(status["state"], "running")
        self.assertIn("filesystem", status["capabilities"])
        self.assertIn("memory", status)

    def test_deny_then_grant_then_call(self):
        denied = self._rpc("call", action="shell.run",
                           extra={"command": "echo x"})["data"]
        self.assertFalse(denied["success"])
        self._rpc("grant", action="shell.run")
        allowed = self._rpc("call", action="shell.run",
                            extra={"command": "echo boot-ok"})["data"]
        self.assertTrue(allowed["success"], allowed)
        self.assertIn("boot-ok", allowed["data"]["stdout"])

    def test_memory_and_caps_over_rpc(self):
        self._rpc("mem_put", key="bootnote", value="hello")
        self.assertEqual(self._rpc("mem_get", key="bootnote")["data"], "hello")
        actions = self._rpc("caps")["data"]["actions"]
        self.assertIn("fs.write", actions)

    def test_shell_facade_over_rpc(self):
        client = _DirectClient(self.server)
        kernel = RemoteKernel(client)
        run = kernel.run_plan("inspect environment")
        self.assertIn(run["status"], ("done", "failed"))
        result = kernel.cap.call("android.info")
        self.assertFalse(result.success)  # deny by default

    def test_unknown_op_raises(self):
        response = self.server.rpc({"op": "bogus_op"})
        self.assertFalse(response["ok"])


class _DirectClient:
    """Bridges RemoteKernel to an in-process server (no file framing)."""

    def __init__(self, server: RuntimeServer):
        self._server = server

    def rpc(self, op: str, **payload) -> dict:
        response = self._server.rpc({"op": op, **payload})
        if response is None:
            raise RuntimeRpcError("no response")
        if not response.get("ok"):
            raise RuntimeRpcError(response.get("error", "rpc failed"))
        return response


class ShutdownSemanticsTests(unittest.TestCase):
    """Shutdown must stop the runtime and release the lock."""

    def test_shutdown_marks_offline(self):
        install, config = _bootstrapped_install()
        server, kernel = _inprocess_server(install, config)
        try:
            response = server.rpc({"op": "shutdown"})
            self.assertEqual(response["ok"], True)
        finally:
            server.close()
        self.assertFalse(RuntimeLock(install).is_online())


class RefuseSecondRuntimeTests(unittest.TestCase):
    def test_inprocess_refuses_second_server(self):
        install, config = _bootstrapped_install()
        first, kernel = _inprocess_server(install, config)
        try:
            from buster.kernel.core import Kernel
            second = RuntimeServer(Kernel(config=config), install)
            self.assertFalse(second.start())
            from buster.runtime import run_daemon
            self.assertEqual(run_daemon(install, config=config), 3)
            self.assertTrue(RuntimeLock(install).is_online())
        finally:
            first.close()


class OfflineClientTests(unittest.TestCase):
    def test_facade_requires_online_runtime(self):
        install = tempfile.mkdtemp()
        client = RuntimeClient(install)
        self.assertFalse(client.is_online())
        with self.assertRaises(RuntimeOfflineError):
            client.rpc("status")


if __name__ == "__main__":
    unittest.main()