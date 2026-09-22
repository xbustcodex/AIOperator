"""Resource / load sensor (CPU, memory, load average)."""

import os
import platform

from buster.perception.base import Sensor


class ResourcesSensor(Sensor):
    """Observes CPU count, load average, memory usage."""

    name = "resources"

    def observe(self) -> dict:
        try:
            with open("/proc/loadavg") as f:
                load = [float(x) for x in f.read().split()[:3]]
        except (OSError, ValueError):
            load = []

        cpus = os.cpu_count() or 1

        try:
            with open("/proc/meminfo") as f:
                mem = {}
                for line in f:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        mem[k] = v.strip()
        except OSError:
            mem = {}

        return {
            "cpus": cpus,
            "load_1m": load[0] if len(load) > 0 else None,
            "load_5m": load[1] if len(load) > 1 else None,
            "load_15m": load[2] if len(load) > 2 else None,
            "mem": mem,
        }