"""Tests for perception sensors."""

import os
import unittest

from buster.perception.base import SensorHub
from buster.perception.battery import BatterySensor
from buster.perception.device import DeviceSensor
from buster.perception.environment import EnvironmentSensor
from buster.perception.network import NetworkSensor
from buster.perception.resources import ResourcesSensor


class PerceptionTests(unittest.TestCase):
    def test_device_sensor(self):
        observation = DeviceSensor().observe()
        self.assertIn("platform", observation)
        self.assertIn("machine", observation)
        self.assertIn("host", observation)
        self.assertIn("phone_host", observation)

    def test_environment_sensor(self):
        observation = EnvironmentSensor().observe()
        self.assertIn("cwd", observation)
        self.assertIn("disk", observation)

    def test_extended_sensors(self):
        battery = BatterySensor().observe()
        self.assertTrue(any(k in battery for k in ("source", "error")))
        self.assertIn("hostname", NetworkSensor().observe())
        self.assertIn("cpus", ResourcesSensor().observe())

    def test_sensor_hub_snapshot(self):
        hub = SensorHub()
        hub.register(DeviceSensor())
        hub.register(EnvironmentSensor())
        snapshot = hub.snapshot()
        self.assertIn("device", snapshot)
        self.assertIn("environment", snapshot)
        self.assertEqual(hub.names(), ["device", "environment"])


if __name__ == "__main__":
    unittest.main()