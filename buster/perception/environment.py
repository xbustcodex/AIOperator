"""Environment sensor: resources and ambient environment facts."""

import os
import shutil

from buster.perception.base import Sensor


class EnvironmentSensor(Sensor):
    """Observations about the running environment."""

    name = "environment"

    def observe(self) -> dict:
        try:
            disk = shutil.disk_usage(os.getcwd())
            disk_info = {
                "total_bytes": disk.total,
                "used_bytes": disk.used,
                "free_bytes": disk.free,
            }
        except OSError:
            disk_info = {"error": "disk usage unavailable"}

        return {
            "cwd": os.getcwd(),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "")),
            "home": os.path.expanduser("~"),
            "disk": disk_info,
            "env_keys": sorted(os.environ.keys()),
        }