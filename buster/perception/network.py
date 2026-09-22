"""Network / connectivity sensor."""

import socket
import shutil

from buster.perception.base import Sensor


class NetworkSensor(Sensor):
    """Observes hostname, local IP(s), and interface list."""

    name = "network"

    def observe(self) -> dict:
        host = socket.gethostname()
        ips = []
        try:
            # all IPv4 addresses
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ips.append(info[4][0])
        except OSError:
            pass

        # Linux interface list
        interfaces = []
        try:
            with open("/proc/net/dev") as f:
                for line in f.readlines()[2:]:
                    parts = line.split(":")
                    if len(parts) == 2:
                        name = parts[0].strip()
                        if name not in ("lo", "sit0", "virbr0"):
                            interfaces.append(name)
        except OSError:
            pass

        return {
            "hostname": host,
            "ips": ips,
            "interfaces": interfaces,
        }