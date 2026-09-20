"""Integration tests: full kernel boot through capabilities, shell and CLI."""

import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from buster.config import Config
from buster.kernel.core import Kernel
from buster.shell.session import InteractiveShell


def _fresh_kernel() -> Kernel:
    install = tempfile.mkdtemp()
    config = Config(config_path=os.path.join(install, "config.json"))
    config.set("install_path", install + os.sep)
    return Kernel(config=config)


class IntegrationTests(unittest.TestCase):
    def test_boot_status_and_shutdown(self):
        kernel = _fresh_kernel()
        kernel.start()
        status = kernel.status()
        self.assertEqual(status["state"], "running")
        self.assertTrue(status["event_router_running"])
        self.assertTrue(status["scheduler_running"])
        self.assertIn("filesystem", status["capabilities"])
        self.assertIn("local", status["ai_providers"])
        kernel.stop()
        self.assertEqual(kernel.status()["state"], "stopped")

    def test_capability_permission_lifecycle(self):
        kernel = _fresh_kernel()
        kernel.start()
        try:
            denied = kernel.cap.call("android.info")
            self.assertFalse(denied.success)
            kernel.permissions.grant("android.info")
            allowed = kernel.cap.call("android.info")
            self.assertTrue(allowed.success)
        finally:
            kernel.stop()

    def test_shell_end_to_end(self):
        kernel = _fresh_kernel()
        kernel.start()
        try:
            shell = InteractiveShell(kernel=kernel)
            kernel.permissions.grant("shell.run")
            result = shell.run_one('run shell.run command="echo integrated"')
            self.assertTrue(result.ok, result.error)
            self.assertIn("integrated", result.data)
        finally:
            kernel.stop()

    def test_memory_persists_across_kernels(self):
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config.json"))
        config.set("install_path", install + os.sep)

        first = Kernel(config=config)
        first.start()
        first.memory.store.put("flag", "persisted")
        first.stop()

        second = Kernel(config=config)
        second.start()
        try:
            self.assertEqual(second.memory.store.get("flag"), "persisted")
        finally:
            second.stop()

    def test_orchestrator_round_trip(self):
        kernel = _fresh_kernel()
        kernel.start()
        try:
            from buster.agents.orchestration import AgentOrchestrator
            agent = AgentOrchestrator(kernel=kernel)
            run = agent.run("inspect environment")
            self.assertEqual(run.status.value, "done")
            self.assertGreaterEqual(kernel.memory.experience.count(), 1)
        finally:
            kernel.stop()

    def test_cli_version_and_status(self):
        from buster.cli import commands
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = commands.cmd_version([])
        self.assertEqual(code, 0)
        self.assertTrue(stdout.getvalue().strip())
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = commands.cmd_help([])
        self.assertEqual(code, 0)
        self.assertIn("shell", stdout.getvalue())

    def test_doctor(self):
        from buster.diagnostics.doctor import run_doctor
        report = run_doctor()
        self.assertGreaterEqual(len(report.checks), 4)


if __name__ == "__main__":
    unittest.main()