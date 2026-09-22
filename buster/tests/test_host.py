"""Tests for the TerminalP / Termux-class host detection and acceptance.

TerminalP is the first-class phone host: Buster must detect it, accept it,
and never refuse to run inside it. Termux-class environments remain valid
for compatibility.
"""

import os
import unittest

import buster.android_integration.device as device


class HostDetectionTests(unittest.TestCase):
    def setUp(self):
        self._original_prefix = device.PREFIX
        self._saved_env = {
            key: os.environ.get(key) for key in ("TERMINALP_VERSION", "TERMUX_VERSION")
        }
        for key in ("TERMINALP_VERSION", "TERMUX_VERSION"):
            os.environ.pop(key, None)

    def tearDown(self):
        device.PREFIX = self._original_prefix
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_desktop_by_default(self):
        device.PREFIX = ""
        self.assertEqual(device.host_identity(), "desktop")
        self.assertFalse(device.is_termux_compatible())
        self.assertFalse(device.is_terminalp())
        self.assertFalse(device.is_termux())

    def test_terminalp_prefix_detected(self):
        device.PREFIX = "/data/data/com.prime.tech/files/usr"
        self.assertEqual(device.host_identity(), "terminalp")
        self.assertTrue(device.is_terminalp())
        self.assertTrue(device.is_termux_compatible())

    def test_terminalp_env_marker_detected(self):
        device.PREFIX = ""
        os.environ["TERMINALP_VERSION"] = "1.0.0"
        self.assertEqual(device.host_identity(), "terminalp")
        self.assertTrue(device.is_termux_compatible())

    def test_termux_compat_detected(self):
        device.PREFIX = "/data/data/com.termux/files/usr"
        self.assertEqual(device.host_identity(), "termux")
        self.assertTrue(device.is_termux())
        self.assertTrue(device.is_termux_compatible())

    def test_generic_android_terminal_detected(self):
        device.PREFIX = "/data/data/com.other/files/usr"
        self.assertEqual(device.host_identity(), "android-terminal")
        self.assertTrue(device.is_termux_compatible())

    def test_device_info(self):
        device.PREFIX = "/data/data/com.prime.tech/files/usr"
        info = device.device_info()
        self.assertEqual(info.host, "terminalp")
        self.assertTrue(info.phone_host)
        self.assertTrue(info.terminalp)


class HostAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self._original_prefix = device.PREFIX
        self._saved_env = {key: os.environ.get(key)
                           for key in ("TERMINALP_VERSION", "TERMUX_VERSION")}
        for key in ("TERMINALP_VERSION", "TERMUX_VERSION"):
            os.environ.pop(key, None)

    def tearDown(self):
        device.PREFIX = self._original_prefix
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_doctor_accepts_terminalp(self):
        from buster.diagnostics.doctor import run_doctor
        device.PREFIX = "/data/data/com.prime.tech/files/usr"
        report = run_doctor()
        host_check = next(c for c in report.checks if c["name"] == "host-environment")
        self.assertTrue(host_check["ok"])
        self.assertIn("terminalp", host_check["detail"])

    def test_installer_accepts_terminalp(self):
        import installer
        device.PREFIX = "/data/data/com.prime.tech/files/usr"
        self.assertTrue(installer.verify_host_environment())

    def test_android_capability_reports_host(self):
        from buster.kernel.core import Kernel
        from buster.config import Config
        import tempfile
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config.json"))
        config.set("install_path", install + os.sep)
        kernel = Kernel(config=config)
        kernel.start()
        try:
            kernel.permissions.grant("android.info")
            result = kernel.cap.call("android.info")
            self.assertTrue(result.success, result.error)
            self.assertEqual(result.data["host"], "desktop")
            self.assertIn("phone_host", result.data)
        finally:
            kernel.stop()


if __name__ == "__main__":
    unittest.main()