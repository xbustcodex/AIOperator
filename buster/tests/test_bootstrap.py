"""Tests for the offline bootstrap, runtime seed and build script."""

import os
import sys
import tempfile
import unittest

from buster.bootstrap import bootstrap_offline, seed_runtime
from buster.config import Config
from buster.kernel.core import Kernel


def _install() -> tuple:
    install = tempfile.mkdtemp()
    config = Config(config_path=os.path.join(install, "config", "config.json"))
    return install, config


class BootstrapOfflineTests(unittest.TestCase):
    def test_first_run_then_idempotent(self):
        install, config = _install()
        first = bootstrap_offline(config, install_path=install)
        self.assertTrue(first["first_run"])
        self.assertGreaterEqual(len(first["layout_created"]), 1)
        second = bootstrap_offline(config, install_path=install)
        self.assertFalse(second["first_run"])
        self.assertEqual(second["layout_created"], [])

    def test_never_constructs_kernel(self):
        import buster.kernel.core as core_module
        calls = []
        original = core_module.Kernel
        def spy(*a, **k):
            calls.append(True)
            return original(*a, **k)
        core_module.Kernel = spy
        install, config = _install()
        try:
            bootstrap_offline(config, install_path=install)
        finally:
            core_module.Kernel = original
        self.assertEqual(calls, [])

    def test_default_config_written_once(self):
        install, config = _install()
        bootstrap_offline(config, install_path=install)
        self.assertTrue(os.path.isfile(config.config_path))
        before = os.path.getmtime(config.config_path)
        bootstrap_offline(config, install_path=install)
        self.assertEqual(os.path.getmtime(config.config_path), before)


class SeedRuntimeTests(unittest.TestCase):
    def test_seeds_once_and_idempotent(self):
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config.json"))
        config.set("install_path", install + os.sep)
        kernel = Kernel(config=config)
        kernel.start()
        try:
            first = seed_runtime(kernel)
            self.assertTrue(first["seeded"])
            self.assertEqual(kernel.memory.knowledge.recall("bootstrap.version"), "0.3.0")
            self.assertGreaterEqual(kernel.memory.experience.count(), 1)
            second = seed_runtime(kernel)
            self.assertFalse(second["seeded"])
            self.assertEqual(kernel.memory.experience.count(), 1)
        finally:
            kernel.stop()


class BuildScriptTests(unittest.TestCase):
    def test_build_smoke(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        build_path = os.path.join(repo, "build.py")
        if not os.path.isfile(build_path):
            self.skipTest("build.py not present")
        result = __import__("subprocess").run(
            [sys.executable, "-W", "ignore", build_path, "--skip-tests"],
            cwd=repo, capture_output=True, text=True, timeout=240,
        )
        combined = (result.stdout or "") + (result.stderr or "")
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("=== Build summary ===", combined, combined)


if __name__ == "__main__":
    unittest.main()