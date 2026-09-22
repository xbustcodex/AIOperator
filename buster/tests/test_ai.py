"""Tests for AI providers and agent orchestration."""

import os
import tempfile
import unittest

from buster.ai_providers.base import AIMessage
from buster.ai_providers.local import LocalProvider
from buster.ai_providers.registry import AIProviderRegistry
from buster.ai_providers.remote import RemoteProvider
from buster.agents.orchestration import AgentOrchestrator
from buster.config import Config
from buster.kernel.core import Kernel


class LocalProviderTests(unittest.TestCase):
    def test_complete(self):
        provider = LocalProvider()
        completion = provider.complete([AIMessage(role="user", content="hello")])
        self.assertEqual(completion.message.role, "assistant")
        self.assertIn("Hello", completion.message.content)

    def test_models(self):
        provider = LocalProvider()
        self.assertIn("buster-local", provider.models())


class ProviderRegistryTests(unittest.TestCase):
    def test_register_and_default(self):
        registry = AIProviderRegistry()
        registry.register(LocalProvider())
        self.assertEqual(registry.get().name, "local")
        self.assertIn("local", registry.names())

    def test_unknown_provider(self):
        registry = AIProviderRegistry()
        registry.register(LocalProvider())
        from buster.ai_providers.registry import ProviderNotFoundError
        with self.assertRaises(ProviderNotFoundError):
            registry.get("missing")


class RemoteProviderTests(unittest.TestCase):
    def test_unconfigured_raises(self):
        provider = RemoteProvider()
        self.assertFalse(provider.configured)
        from buster.ai_providers.base import AIProviderError
        with self.assertRaises(AIProviderError):
            provider.complete([AIMessage(role="user", content="hi")])


class OrchestrationTests(unittest.TestCase):
    def test_fallback_plan_without_provider(self):
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config.json"))
        config.set("install_path", install + os.sep)
        kernel = Kernel(config=config)
        kernel.start()
        try:
            agent = AgentOrchestrator(kernel=kernel)
            run = agent.run("inspect the device", provider="nonexistent")
            self.assertEqual(run.status.value, "done")
            self.assertTrue(isinstance(run.result, dict))
            self.assertGreaterEqual(len(run.result["executed"]), 1)
            self.assertGreaterEqual(kernel.memory.experience.count(), 1)
        finally:
            kernel.stop()


class PlannerAgentTests(unittest.TestCase):
    def test_run_planner_without_provider(self):
        install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(install, "config.json"))
        config.set("install_path", install + os.sep)
        kernel = Kernel(config=config)
        kernel.start()
        try:
            run = kernel.run_planner("inspect the environment")
            self.assertIn(run["status"], ("done", "failed"))
            self.assertGreaterEqual(run["steps"], 0)
            self.assertGreaterEqual(kernel.memory.experience.count(), 1)
            # reflection distilled the run into an "agent_working" knowledge entry
            self.assertTrue(any(k.startswith("agent_working:planner")
                                for k in kernel.memory.knowledge.keys()))
        finally:
            kernel.stop()


if __name__ == "__main__":
    unittest.main()