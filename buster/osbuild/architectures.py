"""Buster OS CPU architecture registry and support policy.

Buster OS is ONE operating system and ONE source tree. Architectures are
release targets, not separate variants. This registry centralizes the
architecture-specific facts the build system needs: Debian archive tokens,
ELF class/machine values, multiarch triplets and expected dynamic loaders.

Support tiers:

* ``enabled`` — a release artifact is produced and structurally verified by
  the distribution pipeline for this architecture.
* ``candidate`` — Debian publishes packages and the full Buster base
  dependency closure resolves for this architecture, but the architecture is
  not yet release-enabled (requires artifact build, structural verification
  and, where the environment permits, runtime execution testing).

Adding another CPU architecture in the future means enabling and testing
another build target in this registry — never forking Buster OS.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArchMeta:
    token: str                  # Debian archive token (amd64, arm64, ...)
    aliases: tuple = ()
    machine: str = ""           # uname -m style
    elf_machine: int = 0        # ELF e_machine value
    elf_class: int = 2          # EI_CLASS: 1 = 32-bit, 2 = 64-bit
    triplet: str = ""           # multiarch triplet
    loaders: tuple = ()         # libc dynamic loader basenames
    tier: str = "candidate"     # "enabled" | "candidate"
    note: str = ""

    def deb_lib_dir(self) -> str:
        return f"usr/lib/{self.triplet}"


ENABLED_TOKEN = "amd64"

ARCH_REGISTRY: dict[str, ArchMeta] = {
    "amd64": ArchMeta(
        token="amd64", aliases=("x86_64",), machine="x86_64",
        elf_machine=62, elf_class=2, triplet="x86_64-linux-gnu",
        loaders=("ld-linux-x86-64.so.2",), tier="enabled",
        note="primary desktop/cloud target",
    ),
    "arm64": ArchMeta(
        token="arm64", aliases=("aarch64",), machine="aarch64",
        elf_machine=183, triplet="aarch64-linux-gnu",
        loaders=("ld-linux-aarch64.so.1",), tier="enabled",
        note="primary mobile/phone target",
    ),
    "armhf": ArchMeta(
        token="armhf", aliases=("armv7l", "armv7l-gnueabihf"), machine="armv7l",
        elf_machine=40, triplet="arm-linux-gnueabihf",
        loaders=("ld-linux-armhf.so.3",), note="32-bit ARM hard-float",
    ),
    "armel": ArchMeta(
        token="armel", machine="armv5tel", elf_machine=40,
        triplet="arm-linux-gnueabi", loaders=("ld-linux.so.3",),
        note="32-bit ARM soft-float",
    ),
    "i386": ArchMeta(
        token="i386", aliases=("x86",), machine="i686", elf_machine=3,
        elf_class=1, triplet="i386-linux-gnu", loaders=("ld-linux.so.2",),
        note="legacy 32-bit x86",
    ),
    "ppc64el": ArchMeta(
        token="ppc64el", aliases=("ppc64le", "powerpc64le"), machine="ppc64le",
        elf_machine=21, triplet="powerpc64le-linux-gnu",
        loaders=("ld64.so.2",), note="64-bit little-endian POWER",
    ),
    "s390x": ArchMeta(
        token="s390x", machine="s390x", elf_machine=22,
        triplet="s390x-linux-gnu", loaders=("ld64.so.1",),
        note="IBM Z big-endian",
    ),
    "riscv64": ArchMeta(
        token="riscv64", machine="riscv64", elf_machine=243,
        triplet="riscv64-linux-gnu", loaders=("ld-linux-riscv64-lp64d.so.1",),
        note="emerging RISC-V 64-bit",
    ),
    "mips64el": ArchMeta(
        token="mips64el", machine="mips64el", elf_machine=8,
        triplet="mips64el-linux-gnuabi64", loaders=("ld-2.31.so",),
        note="MIPS 64-bit little-endian (legacy)",
    ),
}


def lookup(token_or_alias: str) -> ArchMeta:
    token_or_alias = token_or_alias.lower()
    if token_or_alias in ARCH_REGISTRY:
        return ARCH_REGISTRY[token_or_alias]
    for meta in ARCH_REGISTRY.values():
        if token_or_alias in meta.aliases:
            return meta
    raise KeyError(f"unsupported Buster OS architecture: {token_or_alias}")


def enabled() -> list[ArchMeta]:
    return [m for m in ARCH_REGISTRY.values() if m.tier == "enabled"]


def candidates() -> list[ArchMeta]:
    return [m for m in ARCH_REGISTRY.values() if m.tier == "candidate"]


def register(token: str, meta: ArchMeta) -> None:
    """Enable a new architecture target (build definition, not a fork)."""
    ARCH_REGISTRY[token] = meta
    ARCH_REGISTRY[token].__dict__["tier"] = "enabled"


def autodetect_host() -> ArchMeta:
    import platform
    machine = platform.machine().lower()
    return lookup(machine if machine in ARCH_REGISTRY else (
        "arm64" if machine in ("aarch64", "arm64")
        else "amd64" if machine in ("x86_64", "amd64")
        else machine))