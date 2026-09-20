"""Tests for shell parsing, structured results, and the interactive session."""

import os
import tempfile
import unittest

from buster.config import Config
from buster.kernel.core import Kernel
from buster.shell.parser import parse
from buster.shell.results import StructuredResult
from buster.shell.session import InteractiveShell


class ParserTests(unittest.TestCase):
    def test_plain(self):
        command = parse("echo hello world")
        self.assertEqual(command.name, "echo")
        self.assertEqual(command.args, ["hello", "world"])

    def test_quoted(self):
        command = parse("run fs.write path='a b c' content=\"two words\"")
        self.assertEqual(command.args, ["fs.write", "path=a b c", "content=two words"])

    def test_options_long(self):
        command = parse("audit --limit 5")
        self.assertEqual(command.option("limit"), 5)

    def test_boolean_options(self):
        command = parse("run shell.sleep --async")
        self.assertTrue(command.option("async"))

    def test_empty(self):
        self.assertIsNone(parse("   "))


class StructuredResultTests(unittest.TestCase):
    def test_render_ok(self):
        result = StructuredResult.success("echo", "hi")
        self.assertEqual(result.render(), "hi")

    def test_render_failure(self):
        result = StructuredResult.failure("x", "boom")
        self.assertIn("boom", result.render())
        self.assertFalse(result.ok)


class InteractiveShellTests(unittest.TestCase):
    def setUp(self):
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config.json"))
        config.set("install_path", install + os.sep)
        self.kernel = Kernel(config=config)
        self.kernel.start()
        self.shell = InteractiveShell(kernel=self.kernel)

    def tearDown(self):
        self.kernel.stop()

    def test_echo(self):
        result = self.shell.run_one("echo hi")
        self.assertTrue(result.ok)
        self.assertEqual(result.data, "hi")

    def test_version(self):
        result = self.shell.run_one("version")
        self.assertTrue(result.ok)

    def test_caps(self):
        result = self.shell.run_one("caps")
        self.assertTrue(result.ok)
        self.assertIn("filesystem", result.data)

    def test_run_capability_denied_by_default(self):
        result = self.shell.run_one("run android.info")
        self.assertFalse(result.ok)
        self.assertIn("denied", result.error.lower())

    def test_run_capability_granted(self):
        self.kernel.permissions.grant("android.info")
        result = self.shell.run_one("run android.info")
        self.assertTrue(result.ok, result.error)
        self.assertIn("termux", result.data)

    def test_run_with_params(self):
        self.kernel.permissions.grant("python.eval")
        result = self.shell.run_one('run python.eval code="2 ** 8"')
        self.assertTrue(result.ok, result.error)
        self.assertIn("256", result.data)

    def test_jobs_list_and_run_async(self):
        result = self.shell.run_one("jobs")
        self.assertTrue(result.ok)
        scheduled = self.shell.run_one("run android.info --async")
        self.assertTrue(scheduled.ok, scheduled.error)
        self.assertIn("scheduled", scheduled.data)

    def test_grant_deny(self):
        granted = self.shell.run_one("grant fs.exists")
        self.assertTrue(granted.ok)
        denied = self.shell.run_one("deny fs.exists")
        self.assertTrue(denied.ok)

    def test_unknown_command(self):
        result = self.shell.run_one("frobnicate")
        self.assertFalse(result.ok)
        self.assertIn("unknown command", result.error)

    def test_mem_put_get(self):
        put = self.shell.run_one("mem put greeting hello")
        self.assertTrue(put.ok)
        got = self.shell.run_one("mem greeting")
        self.assertTrue(got.ok)
        self.assertEqual(got.data, "hello")


if __name__ == "__main__":
    unittest.main()