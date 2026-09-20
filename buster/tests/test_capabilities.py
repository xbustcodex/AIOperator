"""Tests for the capability registry, lifecycle, adapters and core impls."""

import os
import tempfile
import unittest

from buster.capabilities.adapters import FunctionCapability, LegacyRouterAdapter
from buster.capabilities.registry import CapabilityRegistry
from buster.kernel.core import Kernel
from buster.config import Config


def _make_kernel() -> Kernel:
    install = tempfile.mkdtemp()
    config = Config(config_path=os.path.join(install, "config.json"))
    config.set("install_path", install + os.sep)
    kernel = Kernel(config=config)
    kernel.start()
    return kernel


class CapabilityRegistryTests(unittest.TestCase):
    def test_unknown_action(self):
        registry = CapabilityRegistry()
        result = registry.call("nope.nothing")
        self.assertFalse(result.success)
        self.assertIn("No capability", result.error)

    def test_function_adapter(self):
        registry = CapabilityRegistry()
        registry.register(FunctionCapability(
            name="math",
            handler=lambda ctx: {"value": 1 + 1},
            action_list=["math.add"],
        ))
        result = registry.call("math.add")
        self.assertTrue(result.success)
        self.assertEqual(result.data, {"value": 2})

    def test_legacy_router_adapter(self):
        router = {
            "legacy.info": lambda payload: {"success": True, "data": {"echo": payload["params"]}},
        }
        registry = CapabilityRegistry()
        registry.register(LegacyRouterAdapter(router, name="legacy"))
        result = registry.call("legacy.info", extra={"x": 1})
        self.assertTrue(result.success)
        self.assertEqual(result.data["echo"], {"x": 1})

    def test_register_duplicate_raises(self):
        registry = CapabilityRegistry()
        registry.register(FunctionCapability(name="x", handler=lambda c: True,
                                             action_list=["x.a"]))
        with self.assertRaises(ValueError):
            registry.register(FunctionCapability(name="x", handler=lambda c: True,
                                                 action_list=["x.b"]))


class CoreCapabilityTests(unittest.TestCase):
    def test_filesystem_write_read_list(self):
        kernel = _make_kernel()
        try:
            kernel.permissions.grant("fs.write")
            kernel.permissions.grant("fs.read")
            kernel.permissions.grant("fs.list")
            with tempfile.TemporaryDirectory() as folder:
                target = os.path.join(folder, "hello.txt")
                write = kernel.cap.call("fs.write", extra={"path": target, "content": "hi"})
                self.assertTrue(write.success, write.error)
                read = kernel.cap.call("fs.read", extra={"path": target})
                self.assertTrue(read.success)
                self.assertEqual(read.data, "hi")
                listing = kernel.cap.call("fs.list", extra={"path": folder})
                self.assertTrue(listing.success)
                self.assertIn("hello.txt", listing.data["entries"])
        finally:
            kernel.stop()

    def test_delete_protected_path_denied(self):
        kernel = _make_kernel()
        try:
            kernel.permissions.grant("fs.delete")
            target = os.path.join(kernel.config.get("install_path"), "state")
            os.makedirs(target, exist_ok=True)
            result = kernel.cap.call("fs.delete", extra={"path": target, "recursive": True})
            self.assertFalse(result.success)
            self.assertIn("protected", result.error.lower())
        finally:
            kernel.stop()

    def test_python_eval(self):
        kernel = _make_kernel()
        try:
            kernel.permissions.grant("python.eval")
            result = kernel.cap.call("python.eval", extra={"code": "6 * 7"})
            self.assertTrue(result.success, result.error)
            self.assertEqual(result.data["result"], 42)
        finally:
            kernel.stop()

    def test_shell_run(self):
        kernel = _make_kernel()
        try:
            kernel.permissions.grant("shell.run")
            result = kernel.cap.call("shell.run", extra={"command": "echo buster-ok"})
            self.assertTrue(result.success, result.error)
            self.assertEqual(result.data["exit_code"], 0)
            self.assertIn("buster-ok", result.data["stdout"])
        finally:
            kernel.stop()

    def test_event_lifecycle_emitted(self):
        kernel = _make_kernel()
        try:
            events = []
            kernel.event_router.subscribe("capability.succeeded",
                                          lambda p: events.append(p))
            kernel.permissions.grant("android.info")
            kernel.cap.call("android.info")
            deadline = __import__("time").time() + 1
            while not events and __import__("time").time() < deadline:
                __import__("time").sleep(0.01)
            self.assertTrue(events)
            self.assertEqual(events[0]["action"], "android.info")
        finally:
            kernel.stop()


if __name__ == "__main__":
    unittest.main()