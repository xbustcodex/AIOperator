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

    from buster.install import resolve_install_path
    install = resolve_install_path()

    report.add("python-version",
               ok=sys.version_info >= (3, 10),
               detail=f"{platform.python_version()} (>= 3.10 required)")
    report.add("host-environment",
               ok=is_termux_compatible(),
               detail=f"{host_identity()} ({os.environ.get('PREFIX', 'no PREFIX set')})")
    report.add("buster-install",
               ok=os.path.isdir(install),
               detail=install)
    report.add("buster-config",
               ok=_check_config(install),
               detail=f"{os.path.join(install, 'config', 'config.json')} readable")
    report.add("buster-version", ok=True, detail=f"v{get_version()}")
    report.add("kernel-boot",
               ok=_check_kernel_boot(),
               detail="kernel start/stop round-trip succeeds")

    return report


def _check_config(install: str) -> bool:
    try:
        Config(config_path=os.path.join(install, "config", "config.json"),
                install_path=install)
        return True
    except Exception:  # noqa: BLE001
        return False


def _check_kernel_boot() -> bool:
    try:
        from buster.install import resolve_install_path
        from buster.runtime import runtime_ready
        return runtime_ready(resolve_install_path(), timeout=1.0)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Buster OS Linux-environment diagnostics
# ---------------------------------------------------------------------------

OS_REQUIRED_DIRS = [
    "etc", "usr/bin", "usr/lib", "usr/sbin", "var/lib", "var/log",
    "run", "tmp", "home", "root", "dev", "proc", "sys", "opt", "srv",
]


def read_os_release() -> dict:
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = {}
                for line in handle:
                    line = line.strip()
                    if "=" in line:
                        key, _, value = line.partition("=")
                        data[key.strip()] = value.strip().strip('"')
                return data
        except OSError:
            continue
    return {}


def run_os_doctor() -> DoctorReport:
    """Diagnose the surrounding Linux environment (graceful on any host)."""
    report = DoctorReport()

    os_release = read_os_release()
    report.add("os-release", ok=bool(os_release.get("ID")),
               detail=f"ID={os_release.get('ID', 'unknown')}")
    report.add("buster-identity",
               ok=os_release.get("ID") == "busteros",
               detail=f"ID={os_release.get('ID', 'unknown')} "
                      f"VERSION={os_release.get('VERSION_ID', '?')}")

    missing_dirs = [d for d in OS_REQUIRED_DIRS if not os.path.isdir(os.path.join("/", d))]
    report.add("rootfs-layout", ok=not missing_dirs,
               detail="missing: " + ", ".join(missing_dirs) if missing_dirs else "standard tree present")

    dpkg_status = "/var/lib/dpkg/status"
    has_dpkg = os.path.isfile(dpkg_status)
    report.add("package-database", ok=has_dpkg, detail=dpkg_status)
    if has_dpkg:
        required_pkgs = ["coreutils", "bash", "dpkg", "python3"]
        with open(dpkg_status, "r", encoding="utf-8", errors="replace") as handle:
            status_text = handle.read()
        missing_pkgs = [p for p in required_pkgs
                        if f"Package: {p}" not in status_text]
        report.add("required-packages", ok=not missing_pkgs,
                   detail="missing: " + ", ".join(missing_pkgs) if missing_pkgs else "present")

    for binary in ("bash", "python3", "git", "apt-get"):
        import shutil
        report.add(f"binary:{binary}", ok=shutil.which(binary) is not None,
                   detail=shutil.which(binary) or "not found")

    report.add("machine", ok=True,
               detail=f"{platform.machine()} python={platform.python_version()}")
    return report