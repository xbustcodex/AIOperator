"""Tests for the Buster OS GUI server against the real RPC/client boundary.

The GUI server is a pure client of the Buster daemon: we start a real
in-process RuntimeServer (the single runtime authority) and then drive a
GuiServer over HTTP, asserting real state flows end to end. We also prove the
GUI process never instantiates a Kernel.
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


def _bootstrapped() -> tuple:
    install = tempfile.mkdtemp()
    config = Config(config_path=os.path.join(install, "config.json"))
    config.set("install_path", install + os.sep)
    return install, config


def _start_daemon(install, config):
    kernel = Kernel(config=config)
    server = RuntimeServer(kernel, install)
    if not server.start():
        raise RuntimeError("daemon could not acquire lock")
    threading.Thread(target=server.serve, daemon=True).start()
    return server, kernel


def _start_gui(install):
    from buster.gui.server import GuiServer
    server = GuiServer(install, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.2)
    gui_url = f"http://127.0.0.1:{server.port}"
    return server, gui_url


def _get(url: str, timeout: float = 15.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _get_raw(url: str, timeout: float = 15.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def _post(url: str, payload: dict, timeout: float = 30.0):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


class GuiServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install, cls.config = _bootstrapped()
        cls.daemon, cls.kernel = _start_daemon(cls.install, cls.config)
        cls.gui, cls.url = _start_gui(cls.install)
        # grants so consumer files operations work through real capabilities
        cls.kernel.permissions.grant("fs.list")
        cls.kernel.permissions.grant("fs.read")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.gui.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            cls.daemon.close()
        except Exception:  # noqa: BLE001
            pass

    def test_ping(self):
        status, body = _get(self.url + "/api/ping")
        self.assertEqual(status, 200)
        self.assertEqual(body["gui"], "buster-gui")

    def test_bootstrap(self):
        status, body = _get(self.url + "/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertTrue(body["online"])
        self.assertEqual(body["runtime_state"], "running")
        self.assertTrue(body["buster_version"])

    def test_index_served(self):
        status, body = _get_raw(self.url + "/")
        self.assertEqual(status, 200)
        self.assertIn("<!doctype html>", body.lower())
        self.assertIn("app-orb", body)

    def test_home(self):
        status, body = _get(self.url + "/api/home")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"]["state"], "running")
        self.assertIn("activity", body)

    def test_files_through_capabilities(self):
        status, body = _get(self.url + "/api/files?path=.")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertIn("entries", body["data"])

    def test_chat_round_trip(self):
        status, body = _post(self.url + "/api/chat",
                             {"message": "inspect the environment", "session": "gui-test"})
        self.assertEqual(status, 200)
        self.assertTrue(body["reply"])
        self.assertIn("result", body)
        # Conversation persisted in the real memory store.
        stored = self.kernel.memory.store.get("chat:gui-test")
        self.assertTrue(stored)
        self.assertEqual(stored[-1]["role"], "buster")

    def test_permissions(self):
        status, body = _get(self.url + "/api/permissions")
        self.assertEqual(status, 200)
        self.assertIn("rules", body)
        self.assertIn("elevation_sensitive", body)

    def test_grant_deny(self):
        status, body = _post(self.url + "/api/permissions/grant", {"action": "time.now"})
        self.assertEqual(status, 200)
        self.assertEqual(body["granted"], "time.now")
        self.assertTrue(self.kernel.permissions.check("time.now").allowed)

    def test_goals_and_activity(self):
        status, goals = _get(self.url + "/api/goals")
        self.assertEqual(status, 200)
        self.assertIn("goals", goals)
        status, activity = _get(self.url + "/api/activity")
        self.assertEqual(status, 200)
        self.assertIn("events", activity)

    def test_advanced_health(self):
        status, body = _get(self.url + "/api/advanced/health")
        self.assertEqual(status, 200)
        self.assertIn("runtime", body)

    def test_updates(self):
        status, body = _get(self.url + "/api/updates")
        self.assertEqual(status, 200)
        self.assertTrue(body["buster_version"])
        self.assertFalse(body["updater_available"])

    def test_device(self):
        status, body = _get(self.url + "/api/device")
        self.assertEqual(status, 200)
        self.assertIn("device", body)

    def test_prefs(self):
        status, body = _post(self.url + "/api/prefs", {"key": "name", "value": "Ada"})
        self.assertEqual(status, 200)
        stored = self.kernel.memory.store.get("pref:name")
        self.assertEqual(stored, "Ada")


class GuiOfflineTests(unittest.TestCase):
    def test_offline_returns_503(self):
        install = tempfile.mkdtemp()
        from buster.gui.server import GuiServer
        gui = GuiServer(install, host="127.0.0.1", port=0)
        threading.Thread(target=gui.serve_forever, daemon=True).start()
        time.sleep(0.2)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{gui.port}/api/bootstrap",
                                        timeout=10):
                self.fail("expected 503")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 503)
            self.assertIn("offline", exc.read().decode("utf-8"))
        finally:
            gui.stop()


class GuiNoKernelTests(unittest.TestCase):
    def test_gui_process_never_imports_kernel(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        script = textwrap.dedent(f'''
            import sys, tempfile
            sys.path.insert(0, {repo!r})
            from buster.gui.server import GuiServer
            assert 'buster.kernel.core' not in sys.modules, 'kernel imported'
            install = tempfile.mkdtemp()
            GuiServer(install, host='127.0.0.1', port=0)
            assert 'buster.kernel.core' not in sys.modules, 'kernel imported after GuiServer'
            print('NO-KERNEL-OK')
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
            handle.write(script)
            probe = handle.name
        try:
            completed = subprocess.run(
                [sys.executable, "-W", "ignore", probe],
                capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(probe)
        self.assertIn("NO-KERNEL-OK", completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()