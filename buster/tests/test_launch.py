import os
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

from buster.bootstrap import bootstrap_offline
from buster.config import Config
from buster.install import resolve_install_path
from buster.launch import (ensure_bootstrap, ensure_gui, ensure_runtime, launch,
                           open_ui, _present_via_bridge)
from buster.runtime import RuntimeClient, RuntimeLock, wait_offline, wait_online


class ResolverConsistencyTests(unittest.TestCase):
    def test_explicit_install_is_the_config_authority(self):
        install = tempfile.mkdtemp()
        config_path = os.path.join(install, "config", "config.json")
        config = Config(config_path=config_path, install_path=install)
        config.set("install_path", os.path.join(install, "other"))
        self.assertEqual(config.get("install_path"), install)
        self.assertEqual(resolve_install_path(explicit=install), install)
        self.assertEqual(config.install_path, install)

    def test_config_path_infers_its_install_root(self):
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config", "config.json"))
        self.assertEqual(config.get("install_path"), install)
        self.assertEqual(config.install_path, install)

    def test_explicit_config_path_cannot_repoint_install(self):
        install = tempfile.mkdtemp()
        config_path = os.path.join(install, "config", "config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as handle:
            handle.write('{"install_path": "/different/place"}')
        config = Config(config_path=config_path)
        self.assertEqual(config.get("install_path"), install)


class RuntimeReadinessTests(unittest.TestCase):
    def test_existing_pid_is_not_enough_for_reuse(self):
        install = tempfile.mkdtemp()
        with patch("buster.launch.RuntimeLock") as lock_type, \
             patch("buster.launch.runtime_ready", return_value=False) as ready, \
             patch("buster.launch.recover_wedged_runtime", return_value=True), \
             patch("buster.launch.spawn_daemon") as spawn, \
             patch("buster.launch.wait_online", return_value=True):
            lock_type.return_value.is_online.return_value = True
            lock_type.return_value.read.return_value = {"pid": 123}
            result = ensure_runtime(install, wait=3)
        self.assertEqual(result["action"], "started")
        ready.assert_called()
        spawn.assert_called_once_with(install)

    def test_first_and_second_runtime_reuse_one_daemon(self):
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config", "config.json"),
                        install_path=install)
        bootstrap_offline(config, install_path=install)
        first = ensure_runtime(install, wait=30)
        try:
            second = ensure_runtime(install, wait=3)
            self.assertEqual(first["action"], "started")
            self.assertEqual(second["action"], "reused")
            self.assertEqual(first["pid"], second["pid"])
            self.assertTrue(RuntimeLock(install).is_online())
            self.assertTrue(wait_online(install, timeout=3))
        finally:
            try:
                RuntimeClient(install).rpc("shutdown")
                wait_offline(install, timeout=10)
            except Exception:
                pass

    def test_stale_lock_is_swept_before_start(self):
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config", "config.json"),
                        install_path=install)
        bootstrap_offline(config, install_path=install)
        os.makedirs(os.path.join(install, "state"), exist_ok=True)
        with open(os.path.join(install, "state", "runtime.lock"), "w", encoding="utf-8") as handle:
            handle.write('{"pid": 999999999, "at": 0}')
        result = ensure_runtime(install, wait=60)
        try:
            self.assertEqual(result["action"], "started")
            self.assertTrue(RuntimeLock(install).is_online())
        finally:
            try:
                RuntimeClient(install).rpc("shutdown")
                wait_offline(install, timeout=10)
            except Exception:
                pass

    def test_launch_bootstraps_before_runtime_and_reuses_gui(self):
        install = tempfile.mkdtemp()
        with patch("buster.launch.ensure_bootstrap", return_value={"first_run": True}) as bootstrap, \
             patch("buster.launch.ensure_runtime", return_value={"action": "started", "pid": 1}) as runtime, \
             patch("buster.launch.ensure_gui", return_value={"action": "started", "url": "http://127.0.0.1:8468"}) as gui:
            result = launch(install=install, open_browser=False)
        self.assertTrue(bootstrap.called)
        self.assertTrue(runtime.called)
        self.assertTrue(gui.called)
        self.assertEqual(set(result), {"install", "bootstrap", "runtime", "gui", "url", "opened", "open_reason"})
        self.assertEqual(result["runtime"]["pid"], 1)


class GuiClientTests(unittest.TestCase):
    def test_gui_reuse_is_for_the_same_runtime(self):
        from buster.gui.server import GuiServer
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config", "config.json"),
                        install_path=install)
        bootstrap_offline(config, install_path=install)
        ensure_runtime(install, wait=30)
        gui = GuiServer(install, host="127.0.0.1", port=0)
        thread = threading.Thread(target=gui.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            result = ensure_gui(install, port=gui.port, wait=5)
            self.assertEqual(result["action"], "reused")
            self.assertEqual(result["url"], f"http://127.0.0.1:{gui.port}")
        finally:
            gui.stop()
            try:
                RuntimeClient(install).rpc("shutdown")
                wait_offline(install, timeout=10)
            except Exception:
                pass


class EntryPathTests(unittest.TestCase):
    def test_module_entry_paths_execute(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for command in (["-m", "buster.cli", "version"],
                        ["-m", "buster.gui", "--help"]):
            result = subprocess.run([sys.executable, *command], cwd=repo,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_root_launcher_executes_and_reuses_daemon(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        install = tempfile.mkdtemp()
        env = dict(os.environ)
        env["BUSTER_INSTALL"] = install
        result = subprocess.run(
            [sys.executable, os.path.join(repo, "launcher.py"),
             "--install-path", install],
            cwd=repo, env=env, capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        try:
            self.assertTrue(RuntimeLock(install).is_online())
            self.assertTrue(RuntimeClient(install).rpc("status")["data"]["state"])
            second = subprocess.run(
                [sys.executable, os.path.join(repo, "launcher.py"),
                 "--install-path", install],
                cwd=repo, env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        finally:
            try:
                RuntimeClient(install).rpc("shutdown")
                wait_offline(install, timeout=10)
            except Exception:
                pass


class OpenUiPresentationTests(unittest.TestCase):
    """Presentation is best-effort and ordered behind the typed bridge."""

    URL = "http://127.0.0.1:8468"

    def test_no_open_disables_presentation_entirely(self):
        with patch.dict(os.environ, {"BUSTER_NO_OPEN": "1"}):
            opened, reason = open_ui(self.URL)
        self.assertFalse(opened)
        self.assertIn("BUSTER_NO_OPEN", reason)

    def test_compatible_api_opener_still_wins_when_present(self):
        with patch("shutil.which", return_value="/usr/bin/termux-api"), \
             patch("subprocess.run") as runner, \
             patch("buster.launch._present_via_bridge") as bridge:
            opened, reason = open_ui(self.URL)
        self.assertTrue(opened)
        self.assertIn("termux-api", reason)
        bridge.assert_not_called()
        runner.assert_called_once()

    def test_absent_opener_falls_through_to_the_typed_bridge(self):
        with patch("shutil.which", return_value=None), \
             patch("buster.launch._present_via_bridge",
                   return_value=(True, "presented via the bridge")) as bridge:
            opened, reason = open_ui(self.URL)
        self.assertTrue(opened)
        self.assertIn("bridge", reason)
        bridge.assert_called_once_with(self.URL)

    def test_bridge_success_counts_as_presented(self):
        with patch("shutil.which", return_value=None), \
             patch("buster.launch._present_via_bridge", return_value=(True, "ok")):
            opened, _ = open_ui(self.URL)
        self.assertTrue(opened)

    def test_bridge_failure_falls_through_to_the_printed_url(self):
        with patch("shutil.which", return_value=None), \
             patch("buster.launch._present_via_bridge",
                   return_value=(False, "bridge refused")):
            opened, reason = open_ui(self.URL)
        self.assertFalse(opened)
        self.assertIn("printed URL", reason)

    def test_presentation_failure_never_fails_the_launch(self):
        install = tempfile.mkdtemp()
        with patch("buster.launch.ensure_bootstrap", return_value={}), \
             patch("buster.launch.ensure_runtime",
                   return_value={"action": "started", "pid": 1}), \
             patch("buster.launch.ensure_gui",
                   return_value={"action": "started", "url": self.URL}), \
             patch("buster.launch.open_ui", return_value=(False, "boom")):
            result = launch(install=install, open_browser=True)
        # The runtime and GUI came up; only presentation failed.
        self.assertEqual(result["runtime"]["pid"], 1)
        self.assertFalse(result["opened"])
        self.assertEqual(result["open_reason"], "boom")


class PresentBridgeTests(unittest.TestCase):
    """`_present_via_bridge` invokes the typed `present` verb, nothing else."""

    def test_non_loopback_targets_are_refused_without_invoking_anything(self):
        with patch("subprocess.run") as runner:
            opened, reason = _present_via_bridge("https://evil.example")
        self.assertFalse(opened)
        self.assertIn("non-loopback", reason)
        runner.assert_not_called()

    def test_bridge_is_invoked_with_the_argument_free_present_verb(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=b'{"verb": "present", "ok": true, "ready": true, "url": "http://127.0.0.1:8468"}',
            stderr=b"")
        with patch("subprocess.run", return_value=completed) as runner:
            opened, reason = _present_via_bridge("http://127.0.0.1:8468")
        self.assertTrue(opened)
        self.assertIn("bridge", reason)
        argv = list(runner.call_args[0][0])
        # Exactly the typed verb and nothing else: no URL, path, argv, env or
        # cwd is forwarded to the host.
        self.assertEqual(argv[1:], ["-m", "buster.cli", "exec", "present"])
        self.assertNotIn("http://127.0.0.1:8468", argv)
        self.assertEqual(len(argv), 5)

    def test_unready_document_is_not_treated_as_presented(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=b'{"verb": "present", "ok": true, "ready": false, "error": "runtime offline"}',
            stderr=b"")
        with patch("subprocess.run", return_value=completed):
            opened, reason = _present_via_bridge("http://127.0.0.1:8468")
        self.assertFalse(opened)
        self.assertIn("runtime offline", reason)

    def test_nonzero_exit_and_unparsable_output_are_bounded_failures(self):
        for completed in (
                subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"refused"),
                subprocess.CompletedProcess(args=[], returncode=0, stdout=b"not json", stderr=b"")):
            with patch("subprocess.run", return_value=completed):
                opened, _ = _present_via_bridge("http://127.0.0.1:8468")
            self.assertFalse(opened)

    def test_launcher_failure_is_bounded(self):
        with patch("subprocess.run", side_effect=OSError("no such file")):
            opened, reason = _present_via_bridge("http://127.0.0.1:8468")
        self.assertFalse(opened)
        self.assertIn("unavailable", reason)


if __name__ == "__main__":
    unittest.main()
