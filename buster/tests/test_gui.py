"""Tests for the Buster GUI server against the real RPC/client boundary.

The GUI is a pure client of the Buster daemon. Here we boot a real in-process
runtime (the single source of truth) and drive a GuiServer through HTTP,
proving consumer operations flow through the actual kernel/capability stack
rather than mock data. We also verify the GUI process never constructs a
Kernel.
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.request

from buster.config import Config
from buster.kernel.core import Kernel
from buster.runtime import RuntimeServer


def _install_and_config() -> tuple:
    install = tempfile.mkdtemp()
    config = Config(config_path=os.path.join(install, "config.json"))
    config.set("install_path", install + os.sep)
    return install, config


def _start_runtime(install, config):
    kernel = Kernel(config=config)
    server = RuntimeServer(kernel, install)
    if not server.start():
        raise RuntimeError("runtime could not start")
    threading.Thread(target=server.serve, daemon=True).start()
    return server, kernel


def _start_gui(install):
    from buster.gui.server import GuiServer
    gui = GuiServer(install, host="127.0.0.1", port=0)
    threading.Thread(target=gui.serve_forever, daemon=True).start()
    time.sleep(0.3)
    return gui, f"http://127.0.0.1:{gui.port}"


class LiveRuntimeAssertions(unittest.TestCase):
    """GUI endpoints must reflect real runtime state (no fake data)."""

    @classmethod
    def setUpClass(cls):
        cls.install, cls.config = _install_and_config()
        cls.runtime, cls.kernel = _start_runtime(cls.install, cls.config)
        cls.kernel.permissions.grant("fs.list")
        cls.kernel.permissions.grant("fs.read")
        cls.gui, cls.base = _start_gui(cls.install)

    @classmethod
    def tearDownClass(cls):
        for closer in (cls.gui.stop, cls.runtime.close):
            try:
                closer()
            except Exception:  # noqa: BLE001
                pass

    def _get(self, path):
        status, body = self._get_raw(path)
        return status, json.loads(body)

    def _get_raw(self, path):
        with urllib.request.urlopen(f"{self.base}{path}", timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8")

    def _post(self, path, payload):
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_index_and_orb_mark(self):
        status, body = self._get_raw("/")
        self.assertEqual(status, 200)
        self.assertIn("<!doctype html>", body.lower())
        self.assertIn("app-orb", body)
        status, body = self._get_raw("/assets/orb-mark.svg")
        self.assertEqual(status, 200)
        self.assertIn("<svg", body)

    def test_bootstrap_reports_real_runtime(self):
        _, body = self._get("/api/bootstrap")
        self.assertIn(body["online"], (True, False))
        self.assertEqual(body["runtime_state"], "running")
        self.assertTrue(body.get("buster_version"))

    def test_home_available_and_activity(self):
        _, body = self._get("/api/home")
        self.assertIn("status", body)
        self.assertIn("activity", body)
        self.assertEqual(body["status"]["state"], "running")

    def test_chat_roundtrip_against_real_runtime(self):
        _, body = self._post("/api/chat", {"message": "inspect environment", "session": "t1"})
        self.assertTrue(body.get("reply"))
        self.assertTrue(body.get("result"))
        # Conversation history must be in the real runtime memory store.
        history = self.kernel.memory.store.get("chat:t1")
        self.assertIsInstance(history, list)
        self.assertEqual(history[-1]["role"], "buster")

    def test_files_use_capability_gate(self):
        _, body = self._get("/api/files?path=.")
        self.assertIn("ok", body)
        # deny-by-default must hold: un-granted action fails through the gate
        _, blocked = self._post("/api/fs", {"action": "fs.write", "params": {"path": "/tmp/x", "content": "y"}})
        self.assertFalse(blocked.get("ok", True), "fs.write must be denied by default")

    def test_permissions_list_and_grant(self):
        _, body = self._get("/api/permissions")
        self.assertIn("rules", body)
        _, granted = self._post("/api/permissions/grant", {"action": "time.now"})
        self.assertEqual(granted.get("granted"), "time.now")

    def test_goals_and_device_and_updates(self):
        _, goals = self._get("/api/goals")
        self.assertIn("goals", goals)
        _, device = self._get("/api/device")
        self.assertIn("device", device)
        _, updates = self._get("/api/updates")
        self.assertTrue(updates.get("buster_version"))
        self.assertFalse(updates.get("updater_available"))

    def test_advanced_health(self):
        _, body = self._get("/api/advanced/health")
        self.assertIn("runtime", body)


class OfflineGuiTests(unittest.TestCase):
    def test_offline_returns_503_and_offline_flag(self):
        install = tempfile.mkdtemp()
        from buster.gui.server import GuiServer
        gui = GuiServer(install, host="127.0.0.1", port=0)
        threading.Thread(target=gui.serve_forever, daemon=True).start()
        time.sleep(0.3)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{gui.port}/api/home", timeout=20) as resp:
                self.fail("offline GUI must not return 200")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 503)
            payload = json.loads(exc.read().decode("utf-8"))
            self.assertTrue(payload.get("offline"))
        finally:
            gui.stop()


class NoKernelInGuiProcessTests(unittest.TestCase):
    def test_gui_process_never_imports_or_instantiates_kernel(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        script = textwrap.dedent(f'''
            import sys, tempfile
            sys.path.insert(0, {repo!r})
            from buster.gui.server import GuiServer
            install = tempfile.mkdtemp()
            srv = GuiServer(install, host='127.0.0.1', port=0)
            srv.stop()
            assert 'buster.kernel.core' not in sys.modules, 'GUI imported the Kernel!'
            print('NO-KERNEL-OK')
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
            handle.write(script)
            probe = handle.name
        try:
            completed = subprocess.run(
                [sys.executable, "-W", "ignore", probe],
                capture_output=True, text=True, timeout=60,
            )
        finally:
            os.unlink(probe)
        self.assertIn("NO-KERNEL-OK", completed.stdout,
                      completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()