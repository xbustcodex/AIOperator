"""Tests for the security subsystem: protection, elevation, context."""

import os
import tempfile
import unittest

from buster.security.context import ExecutionContext
from buster.security.elevation import ElevationManager
from buster.security.protection import DeleteProtection, ProtectedPathError


class DeleteProtectionTests(unittest.TestCase):
    def test_unprotected_path_allowed(self):
        protection = DeleteProtection(["re:^/data/", "/system/"])
        protection.ensure_allowed(tempfile.mkdtemp())

    def test_protected_prefix_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            protection = DeleteProtection([folder + os.sep])
            target = os.path.join(folder, "nested", "file")
            with self.assertRaises(ProtectedPathError):
                protection.ensure_allowed(target)

    def test_protect_method(self):
        with tempfile.TemporaryDirectory() as folder:
            protected = os.path.join(folder, "guarded")
            os.makedirs(protected, exist_ok=True)
            protection = DeleteProtection([])
            protection.protect(protected + os.sep)
            self.assertTrue(protection.is_protected(os.path.join(protected, "file")))
            self.assertFalse(protection.is_protected(folder))


class ElevationTests(unittest.TestCase):
    def test_denies_without_approver(self):
        manager = ElevationManager(sensitive={"secret.write"})
        self.assertTrue(manager.requires_elevation("secret.write"))
        self.assertFalse(manager.approve("secret.write"))

    def test_scripted_allowlist(self):
        manager = ElevationManager(sensitive={"big.delete"})
        manager._approval = manager.approve_scripted(allowlist={"big.delete"})
        self.assertTrue(manager.approve("big.delete"))

    def test_default_sensitives(self):
        manager = ElevationManager()
        self.assertTrue(manager.requires_elevation("fs.delete"))
        self.assertTrue(manager.requires_elevation("process.kill"))


class ExecutionContextTests(unittest.TestCase):
    def test_from_inputs(self):
        context = ExecutionContext.from_inputs(
            "fs.write", scope="root", context={"actor": "agent", "workspace": "ws1"},
        )
        self.assertEqual(context.security.actor, "agent")
        self.assertEqual(context.workspace, "ws1")
        self.assertEqual(context.security.scope, "root")
        self.assertIsNotNone(context.as_dict()["actor"])


if __name__ == "__main__":
    unittest.main()