"""Buster OS identity and system-layer templates."""

import json
import os

from buster.install import SYSTEM_INSTALL, SYSTEM_LOG_DIR
from buster.version import get_version


def os_release(version: str = None, id_hint: str = "busteros") -> str:
    version = version or get_version()
    return f"""NAME="Buster OS"
VERSION="{version}"
ID={id_hint}
ID_LIKE=debian
PRETTY_NAME="Buster OS {version}"
HOME_URL="https://busteros.example"
VERSION_ID="{version}"
BUG_REPORT_URL="https://github.com/xbustcodex/AIOperator/issues"
"""


def issue(version: str = None) -> str:
    version = version or get_version()
    return f"Buster OS {version} \\n \\l\\n"


def hosts(hostname: str = "busteros") -> str:
    return f"""127.0.0.1\tlocalhost
127.0.1.1\t{hostname}

# The following lines are desirable for IPv6 capable hosts
::1     ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
"""


def nsswitch_conf() -> str:
    return """passwd:         files systemd
group:          files systemd
shadow:         files
gshadow:        files

hosts:          files dns
networks:       files

protocols:      db files
services:       db files
ethers:         files
rpc:            db files

netgroup:       nis
"""


def apt_sources(arch: str, mirror: str, suite: str, security_mirror: str) -> str:
    return f"""# Buster OS — Debian {suite} sources (upstream Linux foundation).
deb {mirror} {suite} main
deb {mirror} {suite}-updates main
deb {security_mirror} {suite}-security main
# Uncomment contrib/non-free as needed by your deployment.
# deb {mirror} {suite} contrib non-free
"""


def fstab() -> str:
    return """# Buster OS fstab — your deployment adds partitions as appropriate.
proc            /proc           proc    defaults                0       0
sysfs           /sys            sysfs   defaults                0       0
devpts          /dev/pts        devpts  gid=5,mode=620          0       0
tmpfs           /run            tmpfs   defaults                0       0
tmpfs           /dev/shm        tmpfs   mode=1777,nosuid,nodev  0       0
tmpfs           /tmp            tmpfs   defaults                0       0
"""


def buster_config_json(install_path: str = SYSTEM_INSTALL,
                       log_dir: str = SYSTEM_LOG_DIR) -> str:
    return json.dumps({
        "logging_level": "INFO",
        "ai_providers": {},
        "permissions": {},
        "capabilities": {},
        "security": {"elevation_allow": []},
        "install_path": install_path,
        "log_dir": log_dir,
    }, indent=2)


def buster_profile_sh() -> str:
    return """# Buster OS environment
export PATH="$PATH:/opt/buster/bin"
"""


def systemd_unit() -> str:
    return f"""[Unit]
Description=Buster OS runtime daemon
After=network.target local-fs.target

[Service]
Type=simple
EnvironmentFile=/etc/buster/buster.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -m buster.cli daemon
WorkingDirectory=/opt/buster/lib
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def sysvinit_script() -> str:
    return f"""#!/bin/sh
# Buster OS runtime daemon (sysvinit compatibility)
case "$1" in
  start)
    [ -d /run/buster ] || mkdir -p /run/buster
    if [ -f /run/buster/runtime.lock ]; then
      echo "Buster already running"
      exit 0
    fi
    start-stop-daemon --start --background --make-pidfile \\
      --pidfile /run/buster/busterd.pid --startas /usr/bin/buster \\
      -- start
    ;;
  stop)
    /usr/bin/buster stop || true
    ;;
  status)
    /usr/bin/buster status
    ;;
  *)
        echo "Usage: /etc/init.d/buster {{start|stop|status}}"
    exit 1
    ;;
esac
exit 0
"""


def identity_json(version: str, arch: str, foundation: str,
                  foundation_version: str) -> str:
    return json.dumps({
        "os": "Buster OS",
        "version": version,
        "architecture": arch,
        "foundation": foundation,
        "foundation_version": foundation_version,
        "id": "busteros",
    }, indent=2)


def buster_daemon_python(install_path: str) -> str:
    """Small module that starts the Buster daemon with system layout."""
    from textwrap import dedent
    return dedent(f"""
    import sys
    sys.path.insert(0, "/opt/buster/lib")
    from buster.config import Config
    from buster.runtime import run_daemon
    import os
    config = Config(config_path="/etc/buster/config.json", install_path={install_path!r})
    sys.exit(run_daemon({install_path!r}, config=config))
    """)