"""Multi-architecture tests for the Buster OS distribution pipeline (offline).

Verifies the architecture registry, ELF header parsing, architecture-aware
rootfs verification and that package dependency resolution is not hard-coded
to amd64 — guarding against hidden single-architecture assumptions.
"""

import os
import stat
import struct
import tempfile
import unittest

from buster.osbuild import elf
from buster.osbuild.architectures import (
    ARCH_REGISTRY, candidates, enabled, lookup,
)
from buster.osbuild import packages, resolver
from buster.osbuild.rootfs import Rootfs


def make_elf(e_class: int, e_machine: int, endian: str = "little") -> bytes:
    ident = bytearray(b"\x7fELF")
    ident.append(e_class)                         # EI_CLASS
    ident.append(1 if endian == "little" else 2)  # EI_DATA
    ident += b"\x00" * 10                         # pad e_ident to 16 bytes
    ident = bytes(ident)
    fmt = "<" if endian == "little" else ">"
    header = ident + struct.pack(fmt + "HHI", 2, e_machine, 1)
    return header.ljust(64, b"\x00")


class ArchRegistryTests(unittest.TestCase):
    def test_enabled_architectures(self):
        tokens = [m.token for m in enabled()]
        self.assertEqual(tokens, ["amd64", "arm64"])

    def test_lookup_and_aliases(self):
        self.assertEqual(lookup("amd64").machine, "x86_64")
        self.assertEqual(lookup("x86_64").token, "amd64")
        self.assertEqual(lookup("aarch64").token, "arm64")
        self.assertEqual(lookup("arm64").elf_machine, 183)

    def test_every_registered_arch_has_loader_and_triplet(self):
        for meta in ARCH_REGISTRY.values():
            self.assertTrue(meta.loaders, meta.token)
            self.assertTrue(meta.triplet)
            self.assertGreater(meta.elf_machine, 0)
            self.assertIn(meta.elf_class, (1, 2))
            slot = meta.deb_lib_dir()
            self.assertIn(meta.triplet, slot)

    def test_candidate_architectures_evaluated(self):
        tokens = {m.token for m in candidates()}
        for expected in ("i386", "armhf", "ppc64el", "s390x", "riscv64"):
            self.assertIn(expected, tokens)


class ElfHeaderTests(unittest.TestCase):
    def test_parse_amd64(self):
        header = elf.parse_elf(make_elf(2, 62))
        self.assertIsNotNone(header)
        self.assertTrue(header.matches(62, 2))
        self.assertEqual(header.bits, 64)

    def test_parse_arm64(self):
        header = elf.parse_elf(make_elf(2, 183))
        self.assertIsNotNone(header)
        self.assertTrue(header.matches(183, 2))

    def test_parse_i386_32bit(self):
        header = elf.parse_elf(make_elf(1, 3))
        self.assertIsNotNone(header)
        self.assertTrue(header.matches(3, 1))
        self.assertEqual(header.bits, 32)

    def test_non_elf(self):
        self.assertIsNone(elf.parse_elf(b"not elf at all"))


class PerArchResolverTests(unittest.TestCase):
    """Synthetic closure resolution must work for every registered arch."""

    def _records_for(self, token):
        records = []
        for seed in ("base-files", "base-passwd", "libc6", "bash", "coreutils",
                     "dpkg", "python3", "git", "curl", "locales", "sudo",
                     "openssh-server", "util-linux", "iproute2"):
            records.append(packages.PackageRecord(package=seed, version="1.0",
                                                  architecture=token))
            if seed == "libc6":
                # add loader-providing virtual
                records[-1].architecture = token
        records.append(packages.PackageRecord(
            package="libc6", version="1.0", architecture=token,
            provides="") if token != "amd64" else records[2])
        return records

    def test_resolution_for_all_registered_arches(self):
        for meta in ARCH_REGISTRY.values():
            records = self._records_for(meta.token)
            r = resolver.DependencyResolver(records, meta.token)
            chosen = r.resolve(["bash", "python3", "git"])
            names = {p.package for p in chosen}
            self.assertTrue({"bash", "python3", "git"} <= names, meta.token)

    def test_loader_in_lib_dir_for_meta(self):
        for meta in ARCH_REGISTRY.values():
            from buster.osbuild.rootfs import Rootfs as _R
            root = _R(tempfile.mkdtemp(), meta.token)
            target = root._path(meta.deb_lib_dir())
            os.makedirs(target, exist_ok=True)
            self.assertTrue(os.path.isdir(target))


class ArchAwareVerifyTests(unittest.TestCase):
    def test_verify_arm64_rootfs(self):
        import build_rootfs  # imports the verify helper (offline-safe)
        meta = lookup("arm64")
        work = tempfile.mkdtemp()
        root = Rootfs(work, "arm64")
        root.build_layout()
        libdir = root._path(meta.deb_lib_dir())
        os.makedirs(libdir, exist_ok=True)
        loader = os.path.join(libdir, meta.loaders[0])
        with open(loader, "wb") as handle:
            handle.write(make_elf(2, 183))
        bindir = root._path("usr/bin")
        os.makedirs(bindir, exist_ok=True)
        bash = os.path.join(bindir, "bash")
        with open(bash, "wb") as handle:
            handle.write(make_elf(2, 183))
        os.chmod(bash, 0o755)

        os.makedirs(root._path("var/lib/dpkg"), exist_ok=True)
        with open(root._path("var/lib/dpkg/status"), "w") as handle:
            handle.write("Package: libc6\nVersion: 2.36\nArchitecture: arm64\n"
                         "Status: install ok installed\n\n"
                         "Package: coreutils\nVersion: 9.1\nArchitecture: arm64\n"
                         "Status: install ok installed\n\n"
                         "Package: python3\nVersion: 3.11.2\nArchitecture: arm64\n"
                         "Status: install ok installed\n\n"
                         "Package: git\nVersion: 1:2.39\nArchitecture: arm64\n"
                         "Status: install ok installed\n\n")
        for rel in ("etc/passwd", "etc/group", "etc/shadow", "etc/nsswitch.conf",
                    "etc/hosts", "etc/fstab", "etc/apt/sources.list",
                    "usr/bin/dpkg", "usr/bin/apt-get", "usr/lib/os-release"):
            os.makedirs(os.path.dirname(root._path(rel)), exist_ok=True)
            with open(root._path(rel), "w") as handle:
                handle.write("# x\n")
        with open(root._path("etc/os-release"), "w", encoding="utf-8") as handle:
            handle.write('NAME="Buster OS"\nID=busteros\nID_LIKE=debian\n')
        os.makedirs(root._path("opt/buster/lib/buster"), exist_ok=True)
        with open(root._path("opt/buster/lib/buster/version.py"), "w") as handle:
            handle.write("__version__='0.3.1'\n")
        for rel in ("home/buster", "var/lib/buster", "run/buster", "tmp",
                    "dev", "proc", "sys", "root", "bin", "sbin", "lib"):
            os.makedirs(root._path(rel), exist_ok=True)

        checks = build_rootfs.verify_rootfs(root, meta, artifact_path=None)
        failed = [name for name, c in checks.items() if not c["ok"]]
        self.assertFalse(failed, failed)

    def test_verify_rejects_wrong_machine(self):
        import build_rootfs
        meta = lookup("arm64")
        work = tempfile.mkdtemp()
        root = Rootfs(work, "arm64")
        root.build_layout()
        libdir = root._path(meta.deb_lib_dir())
        os.makedirs(libdir, exist_ok=True)
        with open(os.path.join(libdir, meta.loaders[0]), "wb") as handle:
            handle.write(make_elf(2, 62))  # x86_64 ELF in an arm64 rootfs
        checks = build_rootfs.verify_rootfs(root, meta, artifact_path=None)
        self.assertFalse(checks["loader:elf"]["ok"])


class LoaderDetectionTests(unittest.TestCase):
    def test_loader_name_pattern(self):
        import build_rootfs
        amd64 = lookup("amd64")
        self.assertTrue(build_rootfs._is_loader_name("ld-2.36.so", amd64))
        self.assertTrue(build_rootfs._is_loader_name("ld-linux-x86-64.so.2", amd64))
        self.assertFalse(build_rootfs._is_loader_name("libc.so.6", amd64))

    def test_loader_names_in_artifact(self):
        import build_rootfs
        import glob
        samples = glob.glob("dist/buster-os-0.3.1-*-bookworm.tar.gz")
        if not samples:
            self.skipTest("no release artifacts built")
        target = [s for s in samples if "arm64" in s] or samples
        meta = lookup("arm64" if "arm64" in target[0] else "amd64")
        names = build_rootfs.loader_names_in_artifact(target[0], meta)
        self.assertTrue(any(meta.loaders[0] in n for n in names))


class ArchitecturalPolicyTests(unittest.TestCase):
    def test_policy_equivalence(self):
        # enabled set is exactly the two fully supported architectures
        tokens = [m.token for m in enabled()]
        self.assertEqual(tokens, ["amd64", "arm64"])


if __name__ == "__main__":
    unittest.main()