"""Buster OS — root filesystem build system.

Builds the Buster OS Linux environment as a reproducible, populated rootfs
from a mature upstream Linux foundation (Debian), plus the Buster system
layer and the existing Buster runtime/intelligence architecture.

This package is stdlib-only so the distribution can be reconstructed on any
host (including a Windows build machine) without special tooling.
"""

__version__ = "0.3.0"

DISTRO_DEFAULT = "bookworm"
ARCH_DEFAULT = "amd64"
BUSTER_VERSION_UNDER_DEB = "0.3.0"

#: Debian archive layout.
MIRROR_DEFAULT = "http://deb.debian.org/debian"
SECURITY_MIRROR_DEFAULT = "http://security.debian.org/debian-security"
SNAPSHOT_MIRROR_URL = "https://snapshot.debian.org"

#: Base package seeds for the Buster OS standard userspace.
BASE_SEEDS = [
    "base-files", "base-passwd", "libc6", "libgcc-s1", "bash", "coreutils",
    "dash", "diffutils", "findutils", "grep", "sed", "gzip", "tar",
    "dpkg", "apt", "apt-utils", "login", "passwd", "debconf", "debconf-i18n",
    "mount", "util-linux", "procps", "psmisc", "hostname", "debianutils",
    "netbase", "lsb-release", "ca-certificates", "gnupg", "locales",
    "python3", "python3-minimal", "python3-pip", "git", "curl",
    "sudo", "tzdata",
    # strong general-purpose standard userspace
    "less", "nano", "man-db", "openssl", "openssh-server",
    "iproute2", "iputils-ping", "e2fsprogs",
]

#: Buster system directories living under the rootfs.
BUSTER_DIRS = [
    "etc",
    "var/lib/buster",
    "var/lib/buster/state",
    "var/lib/buster/memory",
    "var/cache/buster",
    "var/log/buster",
    "run/buster",
    "opt/buster",
    "opt/buster/lib",
    "opt/buster/bin",
    "srv/buster",
    "home/buster",
]


def autodetect_arch() -> str:
    import platform
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "arm64"
    if machine in ("x86_64", "amd64"):
        return "amd64"
    return ARCH_DEFAULT