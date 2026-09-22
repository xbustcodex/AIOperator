"""Tests for the intelligence layer: nervous system, rhythm, attention,
world model expansion, memory coordinator, learning, reflection, curiosity,
goals, plans, agent roles, proactive analysis, maintenance and providers.
"""

import os
import tempfile
import time
import unittest

from buster.intelligence.attention import Attention
from buster.intelligence.nervous import NervousSystem, Signal
from buster.intelligence.rhythm import CognitiveRhythm, Rhythm
from buster.kernel.world_model import WorldModel


def _artificial_snapshot(battery_pct=80, free_bytes=5 * 1024**3, load=0.1,
                         cpus=8, online=True, host="terminalp", caps=("filesystem", "shell", "android", "search"),
                         providers=("local",), jobs=()):
    return {
        "perception": {
            "battery": {"percentage": battery_pct, "plugged": "USB",
                        "temperature": 30.0},
            "resources": {"load_1m": load, "cpus": cpus,
                          "mem": {"MemAvailable": "8000000 kB", "MemTotal": "8000000 kB"}},
            "network": {"ips": ["127.0.0.1"] if online else [], "hostname": "node"},
            "environment": {"disk": {"free_bytes": free_bytes}},
            "device": {"host": host},
        },
        "kernel": {"state": "running", "capabilities": list(caps),
                   "ai_providers": list(providers), "jobs": list(jobs)},
        "memory": {"store_keys": []},
    }


class NervousSystemTests(unittest.TestCase):
    def test_evaluate_ok_snapshot(self):
        nervous = NervousSystem(None)
        signals = nervous.evaluate(_artificial_snapshot())
        levels = [s.level for s in signals]
        self.assertNotIn("critical", levels)

    def test_battery_low_signal(self):
        nervous = NervousSystem(None)
        signals = nervous.evaluate(_artificial_snapshot(battery_pct=12))
        battery = [s for s in signals if s.kind == "battery"]
        self.assertTrue(battery)
        self.assertEqual(battery[0].level, "warning")

    def test_storage_low_signal(self):
        nervous = NervousSystem(None)
        signals = nervous.evaluate(_artificial_snapshot(free_bytes=0.8 * 1024**3))
        self.assertTrue(any(s.kind == "storage" and s.level == "warning" for s in signals))

    def test_storage_critical_signal(self):
        nervous = NervousSystem(None)
        signals = nervous.evaluate(_artificial_snapshot(free_bytes=100 * 1024**2))
        self.assertTrue(any(s.kind == "storage" and s.level == "critical" for s in signals))

    def test_offline_signal(self):
        nervous = NervousSystem(None)
        signals = nervous.evaluate(_artificial_snapshot(online=False))
        self.assertTrue(any(s.kind == "network" for s in signals))
        # already-offline state does not re-alarm (dedup via last_seen)
        again = nervous.evaluate(_artificial_snapshot(online=False))
        self.assertFalse(any(s.kind == "network" for s in again))

    def test_missing_capability(self):
        nervous = NervousSystem(None)
        signals = nervous.evaluate(_artificial_snapshot(caps=["filesystem"]))
        self.assertTrue(any(s.kind == "capability" and s.level == "warning" for s in signals))

    def test_heed_dedup_and_health(self):
        nervous = NervousSystem(None)
        snapshot = _artificial_snapshot(battery_pct=12)
        first = nervous.heed(snapshot)
        second = nervous.heed(snapshot)
        self.assertGreaterEqual(len(first), 1)
        self.assertEqual(len(second), 0)  # unchanged state is deduplicated
        health = nervous.health()
        self.assertIn(health.overall, ("healthy", "attention", "constrained", "critical"))

    def test_activity_states(self):
        nervous = NervousSystem(None, idle_after=60, sleep_after=120)
        self.assertEqual(nervous.activity_state(), "active")
        nervous._last_activity = time.time() - 90
        self.assertEqual(nervous.activity_state(), "idle")
        nervous._last_activity = time.time() - 200
        self.assertEqual(nervous.activity_state(), "sleep")


class RhythmTests(unittest.TestCase):
    def test_active_when_pending_goals(self):
        rhythm = CognitiveRhythm(None, idle_time=60)
        state = rhythm.transition({"activity": "active", "health": {"overall": "healthy"}},
                                  pending_goals=1)
        self.assertEqual(state, Rhythm.ACTIVE)
        self.assertTrue(rhythm.should_reflect())

    def test_constrained_on_critical(self):
        rhythm = CognitiveRhythm(None)
        state = rhythm.transition({"activity": "active", "health": {"overall": "critical"}},
                                  pending_goals=0)
        self.assertEqual(state, Rhythm.CONSTRAINED)

    def test_sleep_state(self):
        rhythm = CognitiveRhythm(None, idle_time=10)
        state = rhythm.transition({"activity": "sleep", "health": {"overall": "healthy"}},
                                  pending_goals=0, active_jobs=0)
        self.assertEqual(state, Rhythm.SLEEP)

    def test_recovery_after_constrained(self):
        rhythm = CognitiveRhythm(None)
        rhythm.transition({"activity": "active", "health": {"overall": "critical"}}, 0)
        state = rhythm.transition({"activity": "active", "health": {"overall": "healthy"}}, 0)
        self.assertEqual(state, Rhythm.RECOVERY)


class AttentionTests(unittest.TestCase):
    def test_prioritization_and_noise(self):
        attention = Attention(None)
        attention.note_signal("battery", "info", "battery at 60%", rhythm=Rhythm.IDLE)
        critical = attention.note_signal("storage", "critical", "storage critically low",
                                         rhythm=Rhythm.IDLE)
        self.assertIsNotNone(critical)
        top = attention.peek(1)
        self.assertEqual(top[0].kind, "storage")

    def test_noise_suppressed(self):
        attention = Attention(None)
        note = attention.note_signal("host", "info", "running on terminalp",
                                     rhythm=Rhythm.SLEEP)
        self.assertIsNone(note)

    def test_consume(self):
        attention = Attention(None)
        attention.note_signal("job", "warning", "failed job", rhythm=Rhythm.IDLE)
        attention.note_signal("cpu", "warning", "high load", rhythm=Rhythm.IDLE)
        consumed = attention.consume(limit=1)
        self.assertEqual(len(consumed), 1)
        self.assertEqual(len(attention.peek()), 1)


class WorldModelTests(unittest.TestCase):
    def test_observed_and_inferred(self):
        world = WorldModel(None)
        world.observe("battery", 80, source="sensor")
        world.infer("autonomy.ready", True, confidence=0.6, source="reasoning")
        self.assertEqual(world.observed_facts()["battery"]["source"], "sensor")
        self.assertIn("confidence", world.inferred_facts()["autonomy.ready"])
        self.assertEqual(world.get_fact("battery"), 80)

    def test_entities_and_bounded_events(self):
        world = WorldModel(None, history_limit=5)
        world.add_entity("goal-1", "goal", {"title": "x"})
        self.assertEqual(len(world.entities(kind="goal")), 1)
        for i in range(12):
            world.record_event("tick", {"i": i})
        self.assertEqual(len(world.recent_events()), 5)
        world.record_event("tick", {"i": 12})
        world.record_event("tick", {"i": 12})  # adjacent duplicate suppressed
        self.assertLessEqual(len(world.recent_events()), 6)

    def test_snapshot_keys(self):
        world = WorldModel(None)
        snapshot = world.snapshot()
        for key in ("facts", "observed", "inferred", "entities", "events", "components"):
            self.assertIn(key, snapshot)


class MemoryCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        from buster.memory.core import Memory
        from buster.memory.knowledge import KnowledgeMemory
        from buster.memory.experience import ExperienceMemory
        from buster.intelligence.memory import MemoryCoordinator
        self.knowledge = KnowledgeMemory(self.dir)
        self.experience = ExperienceMemory(self.dir)
        self.store = Memory(self.dir)
        self.mc = MemoryCoordinator(self.dir, knowledge=self.knowledge,
                                    experience=self.experience, store=self.store)

    def test_working_memory_ttl(self):
        self.mc.working.put("k", "v", ttl=0.01)
        time.sleep(0.02)
        self.assertIsNone(self.mc.working.get("k"))
        self.mc.working.put("k2", "v2", ttl=60)
        self.assertEqual(self.mc.working.get("k2"), "v2")

    def test_episodic_and_procedural(self):
        self.mc.episodic.record("summary:a", kind="summary", summary="hello world")
        self.assertEqual(len(self.mc.episodic.recall(kind="summary")), 1)
        self.mc.procedural.learn_recipe("build", ["python build.py"])
        self.mc.procedural.record_use("build", True)
        recipe = self.mc.procedural.recipes()[0]
        self.assertEqual(recipe["uses"], 1)
        self.assertEqual(recipe["reliability"], 1.0)

    def test_retrieve_ranking(self):
        self.knowledge.learn("capability_alpha", "handles files", confidence=0.9)
        self.mc.episodic.record("ep: file task", summary="we handled files today")
        results = self.mc.retrieve("files")
        self.assertTrue(results)
        self.assertIn(results[0]["store"], ("knowledge", "episodic", "working"))

    def test_consolidation(self):
        for i in range(4):
            self.experience.record({"target": "repeat-xyz", "status": "failed",
                                    "error": "boom", "ts": time.time()})
        self.store.put("expire-me", "x", ttl=0.001)
        time.sleep(0.01)
        report = self.mc.consolidate()
        self.assertGreaterEqual(report["episodic_summaries"], 1)
        self.assertGreaterEqual(report["expired_store_entries"], 1)

    def test_contradiction_detection(self):
        self.knowledge.learn("pattern:flaky-task", "works", confidence=0.6)
        for _ in range(3):
            self.experience.record({"target": "flaky-task", "status": "failed",
                                    "error": "boom", "ts": time.time()})
        report = self.mc.consolidate()
        self.assertGreaterEqual(report["contradictions"], 1)
        self.assertTrue(self.knowledge.search("contradiction:flaky-task"))


class LearningTests(unittest.TestCase):
    def _kernel(self):
        install = tempfile.mkdtemp()
        from buster.config import Config
        from buster.kernel.core import Kernel
        config = Config(config_path=os.path.join(install, "config.json"))
        config.set("install_path", install + os.sep)
        kernel = Kernel(config=config)
        kernel.start()
        return kernel

    def test_record_cycle_stores_lesson(self):
        kernel = self._kernel()
        try:
            from buster.intelligence.learning import LearningEngine
            learning = LearningEngine(kernel, tempfile.mkdtemp())
            class R:
                success = True
            cycle = learning.record_cycle(
                context="test", intention="goal X", action="fs.list",
                result=R(), evaluation="success", lesson="list first")
            self.assertTrue(cycle.result_ok)
            self.assertTrue(kernel.memory.knowledge.recall("lesson:goal X"))
            self.assertGreaterEqual(kernel.memory.experience.count(), 1)
        finally:
            kernel.stop()

    def test_capability_reliability(self):
        kernel = self._kernel()
        try:
            from buster.intelligence.learning import LearningEngine
            learning = LearningEngine(kernel, tempfile.mkdtemp())
            class R:
                success = True
            learning.record_capability_outcome("fs.list", R())
            outcome = kernel.memory.knowledge.recall("capability_outcome:fs.list")
            self.assertEqual(outcome["uses"], 1)
            self.assertEqual(outcome["reliability"], 1.0)
        finally:
            kernel.stop()


class ReflectionCuriosityTests(unittest.TestCase):
    def _kernel(self):
        install = tempfile.mkdtemp()
        from buster.config import Config
        from buster.kernel.core import Kernel
        config = Config(config_path=os.path.join(install, "config.json"))
        config.set("install_path", install + os.sep)
        kernel = Kernel(config=config)
        kernel.start()
        return kernel

    def test_reflection_produces_items(self):
        kernel = self._kernel()
        try:
            for i in range(3):
                kernel.memory.experience.record({
                    "target": "broken-task", "status": "failed", "error": "boom", "ts": time.time()})
            kernel.memory.experience.record({
                "target": "done-goal", "status": "done", "lesson": "use fs.first",
                "ts": time.time(), "agent": "planner"})
            outputs = kernel.intel.reflection.reflect_now(reason="test")
            self.assertTrue(any(o["kind"] == "question" for o in outputs))
            self.assertTrue(kernel.memory.knowledge.search("hypothesis:"))
        finally:
            kernel.stop()

    def test_curiosity_questions(self):
        kernel = self._kernel()
        try:
            for i in range(2):
                kernel.memory.experience.record({"target": "flaky-goal", "status": "failed",
                                                 "error": "x", "ts": time.time()})
            questions = kernel.intel.curiosity.questions()
            self.assertTrue(any(q["kind"] == "repeated_problem" for q in questions))
        finally:
            kernel.stop()


class GoalPlanAgentTests(unittest.TestCase):
    def setUp(self):
        self.install = tempfile.mkdtemp()
        from buster.config import Config
        from buster.kernel.core import Kernel
        config = Config(config_path=os.path.join(self.install, "config.json"))
        config.set("install_path", self.install + os.sep)
        self.kernel = Kernel(config=config)
        self.kernel.start()

    def tearDown(self):
        self.kernel.stop()

    def test_goal_lifecycle_and_dedup(self):
        goals = self.kernel.intel.goals
        g1 = goals.create("fix the build", kind="system", priority=2)
        g2 = goals.create("fix the build", kind="system")
        self.assertEqual(g1.id, g2.id)  # deduplicated active goal
        goals.complete(g1.id)
        self.assertEqual(goals.get(g1.id).status, "completed")
        goals.create("another", kind="task")
        self.assertEqual(len(goals.active()), 1)

    def test_plan_replanning(self):
        from buster.intelligence.plans import PlanStep
        plans = self.kernel.intel.plans
        plan = plans.create("g-1", "build release")
        self.assertIsNone(plans.update_step(plan.id, 0, "failed"))
        plans.append_steps(plan.id, [PlanStep(action="android.info", reason="fix")])
        self.assertEqual(plans.get(plan.id).replanned, 1)
        self.assertEqual(len(plans.get(plan.id).steps), 1)

    def test_role_agent_allowed_prefix_filter(self):
        from buster.intelligence.agents import RoleAgent
        researcher = RoleAgent(kernel=self.kernel, role="researcher", max_steps=1)
        self.assertTrue(researcher._known_action("search.files"))
        self.assertFalse(researcher._known_action("fs.write"))  # not an allowed prefix
        planner = RoleAgent(kernel=self.kernel, role="planner", max_steps=1)
        self.assertTrue(planner._known_action("fs.write"))

    def test_proactive_and_providers(self):
        for _ in range(2):
            self.kernel.memory.experience.record({"target": "flaky-proc", "status": "failed",
                                                  "error": "boom", "ts": time.time()})
        self.kernel.intel.proactive.tick()
        suggestions = self.kernel.intel.proactive.suggestions()
        self.assertTrue(any(s["kind"] == "recurring_failure" for s in suggestions))
        health = self.kernel.intel.providers.health()
        self.assertTrue(health["local_available"])
        self.assertEqual(self.kernel.intel.providers.select("test"), "local")

    def test_maintenance_diagnostics(self):
        diagnostics = self.kernel.intel.maintenance.diagnostics()
        self.assertIn("runtime", diagnostics)
        self.assertIn("terminalp", diagnostics)
        self.assertIn(diagnostics["overall"], ("healthy", "attention", "degraded"))
        report = self.kernel.intel.maintenance.recover("memory")
        self.assertEqual(report["component"], "memory")


if __name__ == "__main__":
    unittest.main()