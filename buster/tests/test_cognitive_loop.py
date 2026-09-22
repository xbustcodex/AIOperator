"""End-to-end cognitive-loop integration tests.

Proves the complete SENSE → … → ADAPT loop runs through the existing single
Kernel: nervous system, world model, goals, planning, capability execution,
experience, learning, reflection, observability, RPC access, restart
persistence and the single-runtime invariant.
"""

import os
import tempfile
import time
import unittest

from buster.config import Config
from buster.kernel.core import Kernel


def _fresh_kernel(path: str) -> Kernel:
    config = Config(config_path=os.path.join(path, "config.json"))
    config.set("install_path", path + os.sep)
    return Kernel(config=config)


class CognitiveLoopIntegrationTests(unittest.TestCase):
    def test_full_loop_with_grants(self):
        install = tempfile.mkdtemp()
        kernel = _fresh_kernel(install)
        kernel.start()
        try:
            # grant read-safe introspection so the planner can act
            kernel.permissions.grant("android.info")
            kernel.permissions.grant("fs.list")
            kernel.permissions.grant("time.now")

            # sense + attention + rhythm
            kernel.intel.nervous.heed()
            self.assertTrue(kernel.intel_view("nervous")["health"]["overall"] in
                            ("healthy", "attention", "constrained", "critical"))
            self.assertIn(kernel.intel_view("rhythm")["state"],
                          ("active", "idle", "sleep", "constrained", "degraded"))

            # goal -> plan -> act -> observe -> learn -> world update
            result = kernel.process_goal("inspect the environment")
            self.assertEqual(result["status"], "done", result)
            self.assertGreaterEqual(result["steps"], 1)

            goal = kernel.intel.goals.get(result["goal_id"])
            self.assertEqual(goal.status, "completed")
            plan = kernel.intel.plans.get(result["plan_id"])
            self.assertEqual(plan.status, "completed")
            self.assertGreaterEqual(len(plan.steps), 1)

            # experience + learning + knowledge
            self.assertGreaterEqual(kernel.memory.experience.count(), 1)
            self.assertTrue(kernel.memory.knowledge.search("pattern:"))
            self.assertTrue(kernel.memory.knowledge.search("agent_working:"))

            # world model updated with goal entity + events
            self.assertTrue(kernel.world_model.entities(kind="goal"))
            self.assertTrue(any(e["type"] == "goal.processed"
                                for e in kernel.world_model.recent_events(50)))

            # reflection + consolidation work on-demand
            ref = kernel.reflect_now()
            self.assertIsInstance(ref["produced"], list)
            cons = kernel.consolidate_now()
            self.assertIn("episodic_summaries", cons)

            # curiosity + proactive + maintenance + providers observable
            self.assertIsInstance(kernel.intel_view("curiosity")["questions"], list)
            self.assertIsInstance(kernel.intel_view("suggestions")["suggestions"], list)
            self.assertIn("runtime", kernel.intel_view("health"))
            self.assertTrue(kernel.intel_view("providers")["local_available"])
        finally:
            kernel.stop()

    def test_deny_by_default_boundary(self):
        install = tempfile.mkdtemp()
        kernel = _fresh_kernel(install)
        kernel.start()
        try:
            # no grants: the planner's only action is refused by permissions
            kernel.permissions.deny("android.info")
            result = kernel.process_goal("inspect the environment")
            plan = kernel.intel.plans.get(result["plan_id"])
            # steps that ran were denied; plan recorded a failed (or skipped) step
            self.assertIn(plan.status, ("active", "completed", "failed"))
            # learning never granted anything
            self.assertFalse(kernel.permissions.check("fs.write").allowed)
        finally:
            kernel.stop()

    def test_restart_persistence_and_no_duplicates(self):
        install = tempfile.mkdtemp()
        first = _fresh_kernel(install)
        first.start()
        try:
            goal = first.intel.goals.create("persist me", kind="system")
            first.memory.store.put("note", "hello")
            first.memory.experience.record({"target": "persist me", "status": "done",
                                            "ts": time.time()})
        finally:
            first.stop()

        second = _fresh_kernel(install)
        second.start()
        try:
            goal_again = second.intel.goals.create("persist me", kind="system")
            self.assertEqual(goal_again.id, goal.id)  # dedup, no duplicate goal
            self.assertTrue(second.memory.store.get("note") == "hello")
            self.assertEqual(second.intel.orchestrator.state()["tick_scheduled"], True)
            # exactly one cognition job on the scheduler
            cognition_jobs = [j for j in second.scheduler.list_jobs()
                              if j.name == "cognition.tick"]
            self.assertEqual(len(cognition_jobs), 1)
        finally:
            second.stop()

    def test_offline_operation_without_remote_provider(self):
        install = tempfile.mkdtemp()
        kernel = _fresh_kernel(install)
        kernel.start()
        try:
            health = kernel.intel.providers.health()
            self.assertTrue(health["offline_capable"])
            self.assertEqual(kernel.intel.providers.select("anything"), "local")
            # nervous system + world + memory still work with no remote
            kernel.intel.nervous.heed()
            self.assertIn(kernel.intel_view("nervous")["health"]["overall"],
                          ("healthy", "attention", "constrained", "critical"))
            kernel.world_model.observe("host", "terminalp", source="sensor")
            self.assertEqual(kernel.world_model.get_fact("host"), "terminalp")
        finally:
            kernel.stop()


class CognitiveLoopRpcTests(unittest.TestCase):
    def test_intel_via_rpc_server(self):
        install = tempfile.mkdtemp()
        kernel = _fresh_kernel(install)
        import threading
        from buster.runtime import RuntimeServer
        server = RuntimeServer(kernel, install)
        if not server.start():
            self.fail("server could not acquire lock")
        threading.Thread(target=server.serve, daemon=True).start()
        try:
            response = server.rpc({"op": "intel", "section": "nervous"})
            self.assertTrue(response["ok"])
            self.assertIn("health", response["data"])
            response = server.rpc({"op": "intel", "section": "goals"})
            self.assertIn("goals", response["data"])
            goal = server.rpc({"op": "goal", "method": "create",
                               "title": "rpc-goal", "kind": "task"})["data"]
            self.assertTrue(goal["id"])
            reflections = server.rpc({"op": "reflect"})["data"]
            self.assertIsInstance(reflections["produced"], list)
        finally:
            server.close()


if __name__ == "__main__":
    unittest.main()