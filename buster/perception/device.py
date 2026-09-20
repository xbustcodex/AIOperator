"""Device sensor: hardware and Android/Termux platform facts."""

import os
import platform

from buster.perception.base import Sensor


class DeviceSensor(Sensor):
    """Observations about the physical device."""

    name = "device"

    def observe(self) -> dict:
        uname = platform.uname()
        return {
            "platform": sys_platform(),
            "machine": uname.machine,
            "node": uname.node,
            "release": uname.release,
            "python_version": platform.python_version(),
            "prefix": os.environ.get("PREFIX", ""),
            "termux": "termux" in os.environ.get("PREFIX", "").lower(),
            "cpus": os.cpu_count(),
        }


def sys_platform() -> str:
    return platform.system()