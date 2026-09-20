"""Unit tests for kernel lifecycle, scheduler, permissions and audit."""

import tempfile
import time
import unittest

from buster.kernel.audit import Audit
from buster.kernel.permissions import PermissionDenied, Permissions
from buster.kernel.scheduler import JobStatus, Scheduler


class PermissionTests(unittest.TestCase):
    def test_deny_by_default(self):
        permissions = Permissions()
        self.assertFalse(permissions.check("file.read").allowed)

    def test_grant_and_require(self):
        permissions = Permissions()
        permissions.grant("file.read")
        permissions.require("file.read")

    def test_explicit_deny_wins(self):
        permissions = Permissions()
        permissions.grant("file.read")
        permissions.deny("file.read")
        self.assertFalse(permissions.check("file.read").allowed)
        with self.assertRaises(PermissionDenied):
            permissions.require("file.read")


class SchedulerTests(unittest.TestCase):
    def test_one_shot_job(self):
        scheduler = Scheduler()
        scheduler.start()
        flag = {}
        scheduler.schedule("tick", lambda job: flag.setdefault("ran", True), delay=0.05)
        deadline = time.time() + 2
        while "ran" not in flag and time.time() < deadline:
            time.sleep(0.01)
        scheduler.stop()
        self.assertTrue(flag.get("ran"))

    def test_periodic_job(self):
        scheduler = Scheduler()
        scheduler.start()
        counter = {"n": 0}
        def count(job):
            counter["n"] += 1
        scheduler.schedule("beat", count, every=0.05)
        time.sleep(0.25)
        scheduler.stop()
        self.assertGreaterEqual(counter["n"], 2)

    def test_cancel(self):
        scheduler = Scheduler()
        scheduler.start()
        job = scheduler.schedule("nope", lambda j: None, delay=30)
        self.assertTrue(scheduler.cancel(job.id))
        self.assertEqual(scheduler.get(job.id).status, JobStatus.CANCELLED)
        scheduler.stop()


class AuditTests(unittest.TestCase):
    def test_record_and_tail(self):
        audit = Audit(tempfile.mkdtemp())
        audit.record("test.action", "test", {"n": 1})
        entries = audit.tail(1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["action"], "test.action")


if __name__ == "__main__":
    unittest.main()