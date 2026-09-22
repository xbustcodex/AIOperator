"""Environment health checks for Buster OS."""

import os
import platform
import sys
from dataclasses import dataclass, field

from buster.android_integration.device import host_identity, is_termux_compatible
from buster.config import Config
from buster.version import get_version


@dataclass
class DoctorReport:
    checks: list[dict] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "ok": ok, "detail": detail})

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c["ok"])


def run_doctor() -> DoctorReport:
    report = DoctorReport()

    report.add("python-version",
               ok=sys.version_info >= (3, 10),
               detail=f"{platform.python_version()} (>= 3.10 required)")
    report.add("host-environment",
               ok=is_termux_compatible(),
               detail=f"{host_identity()} ({os.environ.get('PREFIX', 'no PREFIX set')})")
    report.add("buster-install",
               ok=os.path.isdir(os.path.expanduser("~/.buster")),
               detail=os.path.expanduser("~/.buster"))
    report.add("buster-config",
               ok=_check_config(),
               detail="~/.buster/config/config.json readable")
    report.add("buster-version", ok=True, detail=f"v{get_version()}")
    report.add("kernel-boot",
               ok=_check_kernel_boot(),
               detail="kernel start/stop round-trip succeeds")

    return report


def _check_config() -> bool:
    try:
        Config(config_path=os.path.join(os.path.expanduser("~/.buster"), "config", "config.json"))
        return True
    except Exception:  # noqa: BLE001
        return False


def _check_kernel_boot() -> bool:
    try:
        from buster.kernel.core import Kernel
        kernel = Kernel(config=Config())
        kernel.start()
        kernel.stop()
        return True
    except Exception:  # noqa: BLE001
        return False