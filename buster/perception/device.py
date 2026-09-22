"""Device sensor: hardware and Android/TerminalP host facts."""

import os
import platform

from buster.android_integration.device import host_identity, is_termux_compatible
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
            "host": host_identity(),
            "phone_host": is_termux_compatible(),
            "cpus": os.cpu_count(),
        }


def sys_platform() -> str:
    return platform.system()