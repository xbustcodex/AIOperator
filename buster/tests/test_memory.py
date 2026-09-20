"""Tests for memory stores, experience log, knowledge and reflection."""

import os
import tempfile
import unittest

from buster.memory.experience import ExperienceMemory
from buster.memory.knowledge import KnowledgeMemory
from buster.memory.reflection import ReflectionEngine, reflect_failures


class ExperienceMemoryTests(unittest.TestCase):
    def test_record_recall(self):
        memory = ExperienceMemory(tempfile.mkdtemp())
        memory.record({"target": "a", "status": "done"})
        memory.record({"target": "b", "status": "failed"})
        self.assertEqual(memory.count(), 2)
        recalled = memory.recall(limit=1)
        self.assertEqual(recalled[-1]["target"], "b")

    def test_capacity_trim(self):
        memory = ExperienceMemory(tempfile.mkdtemp(), capacity=5)
        for i in range(10):
            memory.record({"target": str(i)})
        self.assertLessEqual(memory.count(), 5)


class KnowledgeMemoryTests(unittest.TestCase):
    def test_learn_recall(self):
        knowledge = KnowledgeMemory(tempfile.mkdtemp())
        knowledge.learn("device.cpu", 8, source="sensor", confidence=0.9)
        self.assertEqual(knowledge.recall("device.cpu"), 8)

    def test_confidence_keeps_higher(self):
        knowledge = KnowledgeMemory(tempfile.mkdtemp())
        knowledge.learn("k", "low", confidence=0.2)
        knowledge.learn("k", "high", confidence=0.9)
        self.assertEqual(knowledge.recall("k"), "high")

    def test_persistence(self):
        folder = tempfile.mkdtemp()
        knowledge = KnowledgeMemory(folder)
        knowledge.learn("k", "v")
        reloaded = KnowledgeMemory(folder)
        self.assertEqual(reloaded.recall("k"), "v")


class ReflectionTests(unittest.TestCase):
    def test_reflect_drives_knowledge(self):
        folder = tempfile.mkdtemp()
        knowledge = KnowledgeMemory(folder)
        engine = ReflectionEngine(knowledge=knowledge)
        engine.on_experience({"target": "do x", "status": "failed", "error": "boom"})
        self.assertTrue(any(k.startswith("avoid_repeat:") for k in knowledge.keys()))

    def test_failure_hook(self):
        entry = {"target": "g", "status": "failed", "error": "e"}
        learning = reflect_failures(entry)
        self.assertIsNotNone(learning)
        self.assertEqual(learning["key"], "avoid_repeat:g")


if __name__ == "__main__":
    unittest.main()