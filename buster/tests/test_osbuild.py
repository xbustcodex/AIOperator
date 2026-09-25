"""Tests for the Buster OS Linux distribution build system (offline).

These tests exercise the rootfs builder machinery without network access:
version comparison, dependency parsing/resolution, .deb extraction, rootfs
layout, dpkg status generation, Buster identity/system-layer installation,
v0.2.0 migration, and the OS-environment doctor.
"""

import io
import json
import os
import struct
import tarfile
import tempfile
import time
import unittest

from buster.osbuild import deb, manifest, migrate, packages, resolver
from buster.osbuild.identity import os_release
from buster.osbuild.rootfs import Rootfs
from buster.version import get_version


def make_ar(members: dict[str, bytes]) -> bytes:
    """Build a minimal Unix ar archive for testing (ASCII decimal fields)."""
    out = bytearray(b"!<arch>\n")

    def field(value, width):
        return str(value).rjust(width, " ").encode("ascii")

    for name, data in members.items():
        header = (
            name.encode("utf-8")[:16].ljust(16, b" ")
            + field(0, 12)                 # mtime
            + field(0, 6)                  # uid
            + field(0, 6)                  # gid
            + field(0o100644, 8)           # mode (octal)
            + field(len(data), 10)         # size
            + b"`\n"
        )
        out += header + data
        if len(data) % 2:
            out += b"\n"
    return bytes(out)


def tar_gz_member(path: str, data: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(path)
        info.size = len(data)
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def make_deb(control_text: str, files: dict) -> bytes:
    control = tar_gz_member("./control", control_text.encode())
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as tar:
        for path, content in files.items():
            info = tarfile.TarInfo("./" + path)
            info.size = len(content)
            info.mode = 0o755 if path.startswith("usr/bin/") else 0o644
            tar.addfile(info, io.BytesIO(content))
    return make_ar({
        "debian-binary": b"2.0\n",
        "control.tar.gz": control,
        "data.tar.gz": data.getvalue(),
    })


class VersionCompareTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(resolver.vercmp("1.0", "1.0"), 0)
        self.assertTrue(resolver.vercmp("2.0", "1.9") > 0)
        self.assertTrue(resolver.vercmp("1.9", "1.10") < 0)
        self.assertTrue(resolver.vercmp("1.0-1", "1.0") > 0)  # revision suffix is newer
        self.assertTrue(resolver.vercmp("2:0.1", "1:9.9") > 0)

    def test_epoch(self):
        self.assertTrue(resolver.vercmp("2:0.1", "1:9.9") > 0)

    def test_constraints(self):
        c = resolver.Constraint("pkg", ">=", "1.0")
        self.assertTrue(c.satisfied_by("1.2"))
        self.assertFalse(c.satisfied_by("0.9"))

    def test_parse_depends(self):
        groups = resolver.parse_depends("a (>= 1), b | c")
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0][0].name, "a")
        self.assertEqual(groups[0][0].operator, ">=")
        self.assertEqual({alt.name for alt in groups[1]}, {"b", "c"})


class DebExtractTests(unittest.TestCase):
    def test_extract(self):
        blob = make_deb(
            "Package: hello\nVersion: 1.0\nArchitecture: amd64\n"
            "Maintainer: Test <t@example.com>\nDescription: demo package\n",
            {"usr/bin/hello": b"#!/bin/sh\necho hello\n"})
        content = deb.extract(blob)
        self.assertEqual(content.control["Package"], "hello")
        self.assertIn("usr/bin/hello", content.payload_files)
        with tarfile.open(fileobj=io.BytesIO(
                dict(deb.parse_ar(blob))["data.tar.gz"]), mode="r:*") as tar:
            member = tar.getmember("./usr/bin/hello")
            self.assertEqual(tar.extractfile(member).read(), b"#!/bin/sh\necho hello\n")


class ResolverTests(unittest.TestCase):
    def _record(self, name, version="1.0", arch="amd64", deps="", provides=""):
        return packages.PackageRecord(
            package=name, version=version, architecture=arch, depends=deps,
            provides=provides)

    def test_closure_and_alternatives(self):
        records = [
            self._record("app", deps="libutil (>= 1), alt1 | alt2"),
            self._record("libutil", version="1.2"),
            self._record("alt1"),
            self._record("alt2"),
        ]
        r = resolver.DependencyResolver(records, "amd64")
        chosen = r.resolve(["app"])
        names = sorted(p.package for p in chosen)
        self.assertIn("app", names)
        self.assertIn("libutil", names)
        self.assertTrue({"alt1", "alt2"} & set(names))

    def test_virtual_provides(self):
        records = [
            self._record("tool", deps="cap-provider"),
            self._record("real", provides="cap-provider"),
        ]
        r = resolver.DependencyResolver(records, "amd64")
        chosen = r.resolve(["tool"])
        self.assertTrue(any(p.package == "real" for p in chosen))

    def test_unresolvable_raises(self):
        r = resolver.DependencyResolver([], "amd64")
        with self.assertRaises(KeyError):
            r.resolve(["nonexistent"])


class RootfsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.arch = "amd64"
        self.root = Rootfs(self.dir, self.arch)

    def test_layout_and_merged_usr(self):
        self.root.build_layout()
        for path in ("etc", "usr/bin", "var/lib", "var/log", "tmp", "root",
                     "home", "dev", "proc", "sys", "run", "opt", "srv",
                     "bin", "sbin", "lib"):
            self.assertTrue(os.path.exists(self.root._path(path)), path)
        # merged-/usr: bin/sbin/lib may be symlinks (POSIX) or real dirs elsewhere
        for path, target in (("bin", "usr/bin"), ("sbin", "usr/sbin")):
            if os.path.islink(self.root._path(path)):
                self.assertEqual(os.readlink(self.root._path(path)), target)
            else:
                self.assertTrue(os.path.exists(os.path.join(
                    self.root._path(path), "..", target)) or
                                os.path.isdir(self.root._path(path)))
        self.assertTrue(os.path.isdir(self.root._path("usr/bin")))

    def test_base_config_and_passwd(self):
        self.root.build_layout()
        self.root.write_base_config("bookworm", "http://example/mirror",
                                    "http://example/security")
        self.root.write_passwd_db()
        self.root.write_os_release()
        passwd = open(self.root._path("etc/passwd"), encoding="utf-8").read()
        self.assertIn("root:", passwd)
        self.assertIn("buster:", passwd)
        shadow = open(self.root._path("etc/shadow"), encoding="utf-8").read()
        self.assertIn("root:", shadow)
        os_release_text = open(self.root._path("etc/os-release"), encoding="utf-8").read()
        self.assertIn("busteros", os_release_text)

    def test_install_buster_layer(self):
        self.root.build_layout()
        repo_src = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        self.root.install_buster(repo_src, version=get_version())
        self.root.write_os_release(get_version())
        self.assertTrue(os.path.isfile(
            self.root._path("opt/buster/lib/buster/version.py")))
        self.assertTrue(os.path.exists(self.root._path("opt/buster/bin")))
        service = open(self.root._path("etc/systemd/system/buster.service"),
                       encoding="utf-8").read()
        self.assertIn("buster.cli daemon", service)
        osrelease = open(self.root._path("usr/lib/os-release"), encoding="utf-8").read()
        self.assertIn(f'ID=busteros', osrelease)

    def test_dpkg_status_generation(self):
        self.root.build_layout()
        blob = make_deb(
            "Package: demo\nVersion: 1.0\nArchitecture: all\n"
            "Maintainer: T <t@x>\nDescription: d\n",
            {"usr/share/demo.txt": b"hello"})
        content = deb.extract(blob)
        record = packages.PackageRecord(package="demo", version="1.0",
                                        architecture="all", filename="pool/d.deb")
        self.root.write_dpkg_state([record], {"demo": content})
        status = open(self.root._path("var/lib/dpkg/status"), encoding="utf-8").read()
        self.assertIn("Package: demo", status)
        self.assertIn("Status: install ok installed", status)
        info_list = open(self.root._path("var/lib/dpkg/info/demo.list"),
                         encoding="utf-8").read()
        self.assertIn("/usr/share/demo.txt", info_list)


class IdentityTests(unittest.TestCase):
    def test_os_release(self):
        text = os_release("0.3.0")
        self.assertIn('NAME="Buster OS"', text)
        self.assertIn("busteros", text)
        self.assertIn("debian", text)


class ManifestTests(unittest.TestCase):
    def test_manifest_and_sha(self):
        out = tempfile.mkdtemp()
        artifact = os.path.join(out, "x.bin")
        with open(artifact, "w") as fh:
            fh.write("hello")
        manifest_data = manifest.build_manifest(
            version="0.3.0", arch="amd64", distro="debian", distro_release="bookworm",
            mirror="http://m", snapshot_date="2026-01-01",
            artifact_name="x.bin",
            artifact_sha256=manifest.sha256_file(artifact),
            packages=[{"name": "a", "version": "1", "architecture": "all",
                       "filename": "pool/a", "md5": "", "size": 0}])
        manifest.write_manifest_and_checksums(out, manifest_data)
        with open(os.path.join(out, "manifest.json")) as fh:
            loaded = json.load(fh)
        self.assertEqual(loaded["os"], "Buster OS")
        self.assertTrue(os.path.isfile(os.path.join(out, "SHA256SUMS")))


class MigrateTests(unittest.TestCase):
    def test_migrate_v02(self):
        src = tempfile.mkdtemp()
        os.makedirs(os.path.join(src, "memory"))
        os.makedirs(os.path.join(src, "state"))
        with open(os.path.join(src, "memory", "knowledge.json"), "w") as fh:
            json.dump([{"key": "k", "value": "v", "confidence": 0.9}], fh)
        with open(os.path.join(src, "state", "goals.json"), "w") as fh:
            json.dump([], fh)
        dst = tempfile.mkdtemp()
        report = migrate.migrate_v02(src, dst)
        self.assertTrue(report["migrated"])
        self.assertTrue(os.path.isfile(os.path.join(dst, "memory", "knowledge.json")))
        self.assertTrue(os.path.isfile(os.path.join(dst, "identity.json")))
        again = migrate.migrate_v02(src, dst)
        self.assertFalse(again["migrated"])


class OsDoctorTests(unittest.TestCase):
    def test_os_doctor_runs(self):
        from buster.diagnostics.doctor import run_os_doctor
        report = run_os_doctor()
        self.assertGreaterEqual(len(report.checks), 5)


class FileModePreservationTests(unittest.TestCase):
    """Unix package file modes must survive .deb extraction -> tar archive."""

    def _deb_with_modes(self, control_text: str, files: dict) -> bytes:
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as tar:
            for path, (mode, content) in files.items():
                info = tarfile.TarInfo("./" + path)
                info.size = len(content)
                info.mode = mode
                tar.addfile(info, io.BytesIO(content))
        control = tar_gz_member("./control", control_text.encode())
        return make_ar({
            "debian-binary": b"2.0\n",
            "control.tar.gz": control,
            "data.tar.gz": data.getvalue(),
        })

    def test_modes_survive_from_deb_to_artifact_tar(self):
        work = tempfile.mkdtemp()
        root = Rootfs(work, "amd64")
        root.build_layout()
        blob = self._deb_with_modes(
            "Package: modes-demo\nVersion: 1\nArchitecture: all\n"
            "Maintainer: T <t@x>\nDescription: d\n",
            {
                "usr/bin/tool": (0o755, b"#!/bin/sh\necho tool\n"),
                "usr/share/doc/tool.txt": (0o644, b"docs\n"),
                "etc/modes-demo.conf": (0o640, b"secret\n"),
                "bin/premerge-tool": (0o755, b"#!/bin/sh\necho old-path\n"),
            })
        content = deb.extract(blob)
        data_tar = deb.data_tar(blob)
        installed = root.install_payload("modes-demo", data_tar)

        # merged-/usr relocation
        self.assertIn("/usr/bin/premerge-tool", installed)
        self.assertNotIn("/bin/premerge-tool", installed)

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            root.pack_tree(tar)
        buf.seek(0)
        members = {}
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            for member in tar.getmembers():
                members[member.name] = member

        self.assertEqual(members["usr/bin/tool"].type, tarfile.REGTYPE)
        self.assertEqual(members["usr/bin/tool"].mode & 0o777, 0o755)
        self.assertEqual(members["usr/bin/premerge-tool"].mode & 0o777, 0o755)
        self.assertEqual(members["usr/share/doc/tool.txt"].mode & 0o777, 0o644)
        self.assertEqual(members["etc/modes-demo.conf"].mode & 0o777, 0o640)
        self.assertFalse(bool(members["usr/share/doc/tool.txt"].mode & 0o111))
        self.assertTrue(bool(members["usr/bin/tool"].mode & 0o111))
        # merged-usr layout members are symlinks
        self.assertEqual(members["bin"].type, tarfile.SYMTYPE)
        self.assertEqual(members["bin"].linkname, "usr/bin")
        self.assertEqual(members["lib"].type, tarfile.SYMTYPE)

    def test_symlink_payload_emitted_in_artifact(self):
        work = tempfile.mkdtemp()
        root = Rootfs(work, "amd64")
        root.build_layout()
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as tar:
            link = tarfile.TarInfo("./usr/bin/tool-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "tool"
            link.mode = 0o777
            tar.addfile(link)
            tool = tarfile.TarInfo("./usr/bin/tool")
            tool.mode = 0o755
            tool.size = 4
            tar.addfile(tool, io.BytesIO(b"tool"))
        control = tar_gz_member("./control", b"Package: sym\nVersion: 1\n"
                                          b"Architecture: all\n"
                                          b"Maintainer: T <t@x>\nDescription: d\n")
        blob = make_ar({"debian-binary": b"2.0\n", "control.tar.gz": control,
                        "data.tar.gz": data.getvalue()})
        data_tar = deb.data_tar(blob)
        root.install_payload("sym", data_tar)

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            root.pack_tree(tar)
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            names = {m.name: m for m in tar.getmembers()}
        self.assertEqual(names["usr/bin/tool-link"].type, tarfile.SYMTYPE)
        self.assertEqual(names["usr/bin/tool-link"].linkname, "tool")


class FinalArtifactEntryTests(unittest.TestCase):
    def test_final_archive_has_exact_buster_launchers(self):
        import build_rootfs
        work = tempfile.mkdtemp()
        root = Rootfs(work, "amd64")
        root.build_layout()
        root.install_buster(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), version=get_version())
        artifact = os.path.join(work, "rootfs.tar.gz")
        with tarfile.open(artifact, "w:gz") as tar:
            root.pack_tree(tar)
        checks = build_rootfs.verify_buster_layer(root, artifact)
        failed = [name for name, value in checks.items() if not value["ok"]]
        self.assertFalse(failed, failed)
        with tarfile.open(artifact, "r:gz") as tar:
            for rel in build_rootfs.BUSTER_LAUNCHERS:
                member = tar.getmember(rel)
                self.assertEqual(member.mode & 0o777, 0o755)
                raw = tar.extractfile(member).read()
                self.assertTrue(raw.startswith(b"#!/bin/sh\n"))
                self.assertNotIn(b"\r", raw)

    def test_final_archive_verification_does_not_use_staging(self):
        import build_rootfs
        work = tempfile.mkdtemp()
        root = Rootfs(work, "amd64")
        root.build_layout()
        root.write_binary("usr/bin/buster", b"#!/bin/sh\n", 0o755)
        checks = build_rootfs.verify_buster_layer(root, None)
        self.assertTrue(checks["launcher:present:usr/bin/buster"]["ok"] is False)


if __name__ == "__main__":
    unittest.main()