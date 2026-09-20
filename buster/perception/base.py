"""Sensor abstraction for the perception subsystem.

Future sensor interfaces (battery, gps, camera, geolocation) implement the
same ``observe()`` contract, making new perceptions drop-in additions.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional


class Sensor(ABC):
    """A named source of structured observations."""

    name: str = "sensor"

    def __init__(self):
        self.logger = logging.getLogger(f"buster.perception.{self.name}")

    @abstractmethod
    def observe(self) -> dict:
        """Collect and return the latest observation snapshot."""


class SensorHub:
    """Registry of sensors; collects observations at a moment in time."""

    def __init__(self):
        self._sensors: dict[str, Sensor] = {}
        self.logger = logging.getLogger("buster.perception.hub")

    def register(self, sensor: Sensor) -> None:
        self._sensors[sensor.name] = sensor
        self.logger.debug("Registered sensor '%s'", sensor.name)

    def get(self, name: str) -> Optional[Sensor]:
        return self._sensors.get(name)

    def names(self) -> list[str]:
        return sorted(self._sensors.keys())

    def snapshot(self) -> dict:
        observations = {}
        for name, sensor in self._sensors.items():
            try:
                observations[name] = sensor.observe()
            except Exception:  # noqa: BLE001 - a broken sensor must not break the hub
                observations[name] = {"error": "sensor failed"}
        return observations

    def shutdown(self) -> None:
        self._sensors.clear()