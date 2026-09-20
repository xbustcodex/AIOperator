"""Unit tests for the Buster Config module."""

import os
import tempfile
import unittest

from buster.config import Config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.path = os.path.join(self._tmp, "config", "config.json")

    def test_create_and_reload(self):
        config = Config(config_path=self.path)
        config.set("logging_level", "DEBUG")
        reloaded = Config(config_path=self.path)
        self.assertEqual(reloaded.get("logging_level"), "DEBUG")

    def test_defaults_when_missing(self):
        config = Config(config_path=self.path)
        self.assertEqual(config.get("logging_level"), "INFO")

    def test_nested_access(self):
        config = Config(config_path=self.path)
        config.set_nested("ai_providers.openai.model", "gpt-4o-mini")
        self.assertEqual(config.get_nested("ai_providers.openai.model"), "gpt-4o-mini")
        self.assertIsNone(config.get_nested("does.not.exist"))


if __name__ == "__main__":
    unittest.main()