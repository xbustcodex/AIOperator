"""Tests for the runtime bootstrap and build script."""

import os
import sys
import tempfile
import unittest

from buster.bootstrap import BootstrapManager
from buster.config import Config
from buster.kernel.core import Kernel


def _fresh_kernel() -> Kernel:
    install = tempfile.mkdtemp()
    config = Config(config_path=os.path.join(install, "config.json"))
    config.set("install_path", install + os.sep)
    return Kernel(config=config)


class BootstrapTests(unittest.TestCase):
    def test_first_run_then_idempotent(self):
        kernel = _fresh_kernel()
        kernel.start()
        try:
            manager = BootstrapManager(kernel)
            first = manager.run()
            self.assertTrue(first["first_run"])
            self.assertGreaterEqual(len(first["layout"]), 1)
            second = manager.run()
            self.assertFalse(second["first_run"])
            self.assertEqual(second["layout"], [])
        finally:
            kernel.stop()

    def test_default_grants_applied_from_config(self):
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config.json"))
        config.set("install_path", install + os.sep)
        config.set_nested("security.default_grants", ["android.info", "python.version"])
        kernel = Kernel(config=config)
        kernel.start()
        try:
            manager = BootstrapManager(kernel)
            summary = manager.run()
            self.assertIn("android.info", summary["grants_applied"])
            self.assertIn("python.version", summary["grants_applied"])
            self.assertTrue(kernel.permissions.check("android.info").allowed)
        finally:
            kernel.stop()

    def test_seeds_memory_and_world_model(self):
        kernel = _fresh_kernel()
        kernel.start()
        try:
            manager = BootstrapManager(kernel)
            summary = manager.run()
            self.assertGreaterEqual(kernel.memory.experience.count(), 1)
            self.assertEqual(kernel.memory.knowledge.recall("bootstrap.version"), "0.1.0")
            self.assertEqual(kernel.world_model.get_fact("install_path"),
                             summary["install_path"])
        finally:
            kernel.stop()


class BuildScriptTests(unittest.TestCase):
    def test_build_smoke(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        build_path = os.path.join(repo, "build.py")
        if not os.path.isfile(build_path):
            self.skipTest("build.py not present")
        # Run build in non-test mode to avoid recursive test discovery.
        result = __import__("subprocess").run(
            [sys.executable, "-W", "ignore", build_path, "--skip-tests"],
            cwd=repo, capture_output=True, text=True, timeout=240,
        )
        combined = (result.stdout or "") + (result.stderr or "")
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("=== Build summary ===", combined, combined)


if __name__ == "__main__":
    unittest.main()