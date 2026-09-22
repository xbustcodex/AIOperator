"""Battery sensor (host API + /sys fallback)."""

import os

from buster.perception.base import Sensor


class BatterySensor(Sensor):
    """Observes battery level and charging state."""

    name = "battery"

    def observe(self) -> dict:
        # Prefer the TerminalP / Termux-class Android API binary
        from buster.android_integration import api_binary, termux_api
        info = termux_api.battery()
        if info:
            return {
                "percentage": info.get("percentage"),
                "charging": info.get("plugged") in ("AC", "USB", "Wireless"),
                "health": info.get("health"),
                "temperature": info.get("temperature"),
                "source": api_binary() or "host-api",
            }

        # Fallback: Linux /sys
        battery_dir = "/sys/class/power_supply"
        for name in ("battery", "BAT0", "BAT1"):
            path = os.path.join(battery_dir, name)
            if os.path.isdir(path):
                try:
                    with open(os.path.join(path, "capacity")) as f:
                        pct = int(f.read().strip())
                    status = ""
                    with open(os.path.join(path, "status")) as f:
                        status = f.read().strip()
                    charging = status.lower() in ("charging", "full")
                    return {
                        "percentage": pct,
                        "charging": charging,
                        "status": status,
                        "source": "sysfs",
                    }
                except (OSError, ValueError):
                    continue
        return {"error": "no battery info available"}