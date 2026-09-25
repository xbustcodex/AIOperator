#!/usr/bin/env python3
"""Buster OS Linux distribution builder (per-architecture).

Reproducibly constructs a populated Buster OS rootfs for a target CPU
architecture from the upstream Linux foundation (Debian stable), installs the
Buster system layer and the existing Buster runtime, and emits a deployable
distribution/rootfs artifact with architecture-specific manifests, ELF-aware
verification and checksums.

Usage:
    python build_rootfs.py --arch amd64
    python build_rootfs.py --arch arm64

Architectures are release targets of ONE Buster OS; see
buster/osbuild/architectures.py for the support policy.
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buster.osbuild import BASE_SEEDS, DISTRO_DEFAULT  # noqa: E402
from buster.osbuild import apiclient, deb, elf, manifest, packages, resolver  # noqa: E402
from buster.osbuild.architectures import lookup  # noqa: E402
from buster.osbuild.rootfs import Rootfs  # noqa: E402
from buster.version import get_version  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("build_rootfs")


def parse_args(argv: list | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Buster OS rootfs builder")
    parser.add_argument("--arch", required=True, help="target architecture token")
    parser.add_argument("--distro", default=DISTRO_DEFAULT, help="Debian suite")
    parser.add_argument("--mirror", default="http://deb.debian.org/debian")
    parser.add_argument("--security-mirror",
                        default="http://security.debian.org/debian-security")
    parser.add_argument("--out", default="dist")
    parser.add_argument("--buster-source", default=os.path.dirname(os.path.abspath(__file__)))
    parser.add_argument("--keep", action="store_true",
                        help="keep the working rootfs tree")
    parser.add_argument("--limit", type=int, default=0,
                        help="limit package downloads (debug)")
    return parser.parse_args(argv)


def fetch_index(mirror, arch, distro):
    base = f"{mirror.rstrip('/')}/dists/{distro}/main"
    indexes = {}
    for index_arch in (arch, "all"):
        url = f"{base}/binary-{index_arch}/Packages"
        try:
            indexes[index_arch] = packages.parse_packages(
                apiclient.fetch_packages_index(url + ".gz"))
            log.info("index %s: %d packages", index_arch, len(indexes[index_arch]))
        except Exception as exc:  # noqa: BLE001
            log.warning("index %s unavailable: %s", index_arch, exc)
    return indexes


def resolve_closure(records, arch_token):
    """Resolve the base package closure for an architecture."""
    resolver_ = resolver.DependencyResolver(records, arch_token)
    return resolver_.resolve(list(BASE_SEEDS))


def build_arch(arch_token: str, *, distro: str, mirror: str,
               security_mirror: str, out_dir: str, buster_source: str,
               keep: bool = False, limit: int = 0) -> dict:
    """Build one architecture. Returns paths to produced artifacts."""
    workdir = tempfile.mkdtemp(prefix=f"buster-rootfs-{arch_token}-")
    try:
        return _build_arch_in(arch_token, workdir, distro=distro, mirror=mirror,
                              security_mirror=security_mirror, out_dir=out_dir,
                              buster_source=buster_source, limit=limit)
    finally:
        if keep:
            log.info("rootfs workdir kept at %s", os.path.join(workdir, "rootfs"))
        else:
            shutil.rmtree(workdir, ignore_errors=True)


def _build_arch_in(arch_token: str, workdir: str, *, distro: str, mirror: str,
                   security_mirror: str, out_dir: str, buster_source: str,
                   limit: int = 0) -> dict:
    meta = lookup(arch_token)
    version = get_version()
    snapshot_date = datetime.date.today().isoformat()

    rootfs_dir = os.path.join(workdir, "rootfs")
    root = Rootfs(rootfs_dir, arch_token)

    log.info("Buster OS %s distribution build (arch=%s machine=%s foundation=%s)",
             version, arch_token, meta.machine, distro)
    root.build_layout()
    indexes = fetch_index(mirror, arch_token, distro)
    records = [rec for idx in indexes.values() for rec in idx]
    if not records:
        raise RuntimeError(f"no package index available from {mirror} for {arch_token}")

    try:
        selected = resolve_closure(records, arch_token)
    except KeyError as exc:
        raise RuntimeError(f"dependency resolution failed for {arch_token}: {exc}")

    contents: dict[str, deb.DebContent] = {}
    package_manifest = []
    mirror_base = mirror.rstrip("/")
    used_records = selected[:limit] if limit else selected
    for num, record in enumerate(used_records, 1):
        filename = record.filename
        if not filename:
            continue
        url = f"{mirror_base}/{filename.lstrip('/')}"
        log.info("[%d/%d] %s %s", num, len(used_records), record.package, record.version)
        raw = apiclient.fetch_bytes(url, timeout=90)
        if record.md5sum and hashlib.md5(raw).hexdigest() != record.md5sum:
            log.warning("md5 mismatch for %s (%s)", record.package, record.filename)
        content = deb.extract(raw)
        contents[record.package] = content
        data_tar = deb.data_tar(raw)
        installed = root.install_payload(record.package, data_tar)
        content.payload_files = installed
        package_manifest.append({
            "name": record.package, "version": record.version,
            "architecture": record.architecture, "filename": filename,
            "md5": record.md5sum, "size": record.size,
        })

    root.write_dpkg_state(used_records, contents)
    root.write_base_config(distro, mirror, security_mirror)
    root.write_passwd_db()
    root.write_os_release(version)
    root.install_buster(buster_source, version)

    artifact_name = f"buster-os-{version}-{arch_token}-{distro}.tar.gz"
    artifact_path = os.path.join(out_dir, artifact_name)
    os.makedirs(out_dir, exist_ok=True)
    if os.path.isfile(artifact_path):
        os.remove(artifact_path)
    with tarfile.open(artifact_path, "w:gz") as tar:
        root.pack_tree(tar)

    checks = verify_rootfs(root, meta, artifact_path)
    passed = sum(1 for v in checks.values() if v.get("ok"))
    log.info("rootfs verification (%s): %d/%d checks passed", arch_token, passed, len(checks))

    manifest_data = manifest.build_manifest(
        version=version, arch=arch_token, distro="debian", distro_release=distro,
        mirror=mirror, snapshot_date=snapshot_date,
        artifact_name=artifact_name,
        artifact_sha256=manifest.sha256_file(artifact_path),
        packages=package_manifest)
    manifest_data["machine"] = meta.machine
    manifest_data["tier"] = meta.tier

    manifest_path = os.path.join(out_dir, f"manifest-{arch_token}.json")
    manifest.write_manifest_and_checksums(out_dir, manifest_data, name=manifest_path)

    verification_path = os.path.join(out_dir, f"verification-{arch_token}.json")
    with open(verification_path, "w", encoding="utf-8") as handle:
        json.dump({
            "os": "Buster OS", "version": version,
            "architecture": arch_token, "machine": meta.machine,
            "runtime_executed": False,
            "method": "constructed + structural verification",
            "checks": checks,
        }, handle, indent=2)

    print(f"Buster OS {version} rootfs artifact ({arch_token}): {artifact_path}")
    print(f"verification ({arch_token}): {passed}/{len(checks)}")
    return {
        "arch": arch_token, "machine": meta.machine, "tier": meta.tier,
        "artifact": artifact_path,
        "manifest": manifest_path, "verification": verification_path,
        "checks_passed": passed, "checks_total": len(checks),
    }


def verify_rootfs(root: Rootfs, meta, artifact_path: str) -> dict:
    """Constructed+structural verification, fully architecture-aware."""
    checks: dict[str, dict] = {}
    arch = meta.token

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks[name] = {"ok": ok, "detail": detail}

    required = [
        "etc/os-release", "etc/passwd", "etc/group", "etc/shadow",
        "etc/nsswitch.conf", "etc/hosts", "etc/fstab", "etc/apt/sources.list",
        "usr/bin/dpkg", "usr/bin/apt-get", "var/lib/dpkg/status",
        "usr/lib/os-release", "opt/buster/lib/buster/version.py",
        "home/buster", "var/lib/buster", "run/buster", "tmp", "dev", "proc",
        "sys", "root", "bin", "sbin", "lib",
    ]
    for path in required:
        check(f"exists:{path}", os.path.exists(root._path(path)))

    # package database reports the target architecture
    status_text = read_text(root, "var/lib/dpkg/status")
    check("dpkg:arch-present", f"Architecture: {arch}" in status_text
          or f"{arch} " in status_text,
          f"Architecture: {arch}")
    for pkg in ("coreutils", "python3", "git"):
        check(f"packages:{pkg}", f"Package: {pkg}" in status_text)

    # merged-/usr binaries
    def binary_file(name: str):
        for rel in (f"usr/bin/{name}", f"bin/{name}", f"usr/bin/{name}3"):
            candidate = root._path(rel)
            if os.path.isfile(candidate):
                return candidate
        return None

    bash_path = binary_file("bash")

    # dynamic loader for the target architecture
    loader_path = find_loader(root, meta)
    check("loader:present", loader_path is not None,
          ", ".join(meta.loaders) or "unknown")
    if loader_path:
        header = elf.parse_elf(load_bytes(loader_path))
        check("loader:elf", header is not None and header.matches(meta.elf_machine, meta.elf_class),
              f"e_machine={header.e_machine if header else None} "
              f"class={header.e_class if header else None}")
    tar_names = loader_names_in_artifact(artifact_path, meta)
    if artifact_path:
        check("loader:artifact-symlink", bool(tar_names),
              ", ".join(tar_names) or "public loader name not present in artifact tar")
    else:
        checks["loader:artifact-symlink"] = {"ok": True, "detail": "no artifact given (skipped)"}
    if bash_path:
        header = elf.parse_elf(load_bytes(bash_path))
        check("bash:elf", header is not None and header.matches(meta.elf_machine, meta.elf_class),
              f"e_machine={header.e_machine if header else None} "
              f"class={header.e_class if header else None}")

    osrelease = read_text(root, "etc/os-release")
    check("identity:busteros", "ID=busteros" in osrelease)
    check("identity:ID_LIKE-debian", "ID_LIKE" in osrelease)
    check("buster:installed", os.path.isfile(
        root._path("opt/buster/lib/buster/version.py")))
    check("tooling:dpkg", os.path.isfile(root._path("usr/bin/dpkg")))
    checks.update(verify_buster_layer(root, artifact_path))
    checks.update(verify_tar_metadata(artifact_path, meta))
    return checks


def read_tar_member_index(tar_path: str) -> dict:
    """name -> (type_char, mode) for every member of a release tarball."""
    index = {}
    if not tar_path:
        return index
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            clean = member.name.rstrip("/")
            if clean:
                index[clean] = (member.type, member.mode)
    return index


# ---------------------------------------------------------------------------
# Buster-owned Linux layer verification (Windows-build -> Linux-artifact)
# ---------------------------------------------------------------------------

#: Buster-generated launchers: must be LF-only, valid shebang, executable.
BUSTER_LAUNCHERS = ("usr/bin/buster", "usr/bin/busterctl", "usr/bin/buster-gui")

#: Other Buster-generated scripts/config that must never carry CRLF.
BUSTER_TEXT_FILES = (
    "etc/init.d/buster",
    "etc/profile.d/buster.sh",
    "etc/buster/config.json",
    "etc/buster/buster.env",
    "usr/share/buster/identity.json",
    "usr/share/buster/VERSION",
)

#: Python modules reachable through a ``python -m`` entry point.
BUSTER_ENTRY_MODULES = (
    "opt/buster/lib/buster/cli/__main__.py",
    "opt/buster/lib/buster/gui/__main__.py",
    "opt/buster/lib/buster/gui/server.py",
    "opt/buster/lib/buster/system/busterctl.py",
)


def _tar_bytes(tar_path: str, name: str) -> bytes | None:
    if not tar_path:
        return None
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            member = tar.getmember(name)
            if not member.isfile():
                return None
            handle = tar.extractfile(member)
            return handle.read() if handle else None
    except (KeyError, tarfile.TarError, OSError):
        return None


def verify_buster_layer(root: Rootfs, artifact_path: str) -> dict:
    """Verify Buster-owned launchers and entry points from archive bytes."""
    checks: dict[str, dict] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks[name] = {"ok": bool(ok), "detail": detail}

    if not artifact_path or not os.path.isfile(artifact_path):
        for rel in BUSTER_LAUNCHERS:
            check(f"launcher:present:{rel}", False, "archive missing")
        return checks

    with tarfile.open(artifact_path, "r:gz") as tar:
        members = {member.name.rstrip("/"): member for member in tar.getmembers()}

        def archived(rel: str):
            member = members.get(rel)
            if member is None or not member.isfile():
                return None, b""
            handle = tar.extractfile(member)
            return member, handle.read() if handle is not None else b""

        for rel in BUSTER_LAUNCHERS:
            member, raw = archived(rel)
            check(f"launcher:present:{rel}", member is not None and bool(raw), rel)
            crlf = b"\r\n" in raw
            bare_cr = b"\r" in raw.replace(b"\r\n", b"")
            check(f"launcher:lf-only:{rel}", not (crlf or bare_cr),
                  "LF-only" if not (crlf or bare_cr) else "CR/CRLF found")
            first_line = raw.split(b"\n", 1)[0]
            check(f"launcher:shebang:{rel}", first_line == b"#!/bin/sh",
                  first_line.decode("ascii", "replace")
                  if first_line else "missing shebang")
            check(f"launcher:mode:{rel}",
                  member is not None and (member.mode & 0o777) == 0o755,
                  oct(member.mode & 0o777) if member is not None else "missing")
            text = raw.decode("utf-8", "replace")
            pinned = ("/var/lib/buster" in text
                      or "--install-path" in text
                      or "BUSTER_INSTALL=" in text)
            check(f"launcher:no-hardcoded-path:{rel}", not pinned,
                  "resolved at runtime" if not pinned else "hard-coded install path")

        for rel in BUSTER_TEXT_FILES:
            member, raw = archived(rel)
            if member is not None:
                check(f"text:lf-only:{rel}", b"\r" not in raw,
                      "LF-only" if b"\r" not in raw else "CR found")

        member, config_raw = archived("etc/buster/config.json")
        config_text = config_raw.decode("utf-8", "replace")
        check("config:canonical-install", member is not None
              and '"install_path"' in config_text
              and "/var/lib/buster" in config_text,
              "/var/lib/buster declared in archive config")

        for rel in BUSTER_ENTRY_MODULES:
            member, raw = archived(rel)
            if member is None:
                check(f"entry:present:{rel}", False, "missing from archive")
                continue
            source = raw.decode("utf-8", "replace")
            if "sys.exit(" in source:
                check(f"entry:sys-import:{rel}",
                      re.search(r"^import sys$", source, re.M) is not None,
                      "imports sys")

    return checks


def verify_tar_metadata(tar_path: str, meta) -> dict:
    """Verify Unix metadata as actually recorded in the release tarball."""
    out: dict[str, dict] = {}
    if not tar_path:
        return out  # no artifact provided; metadata checks are skipped
    index = read_tar_member_index(tar_path)

    def entry(name: str):
        return index.get(name) or index.get("./" + name)

    def is_exec(mode: int) -> bool:
        return bool(mode & 0o111)

    # representative executables must be executable in the archive
    execs = []
    for probe in ("usr/bin/bash", "usr/bin/ls", "bin/bash", "bin/ls",
                  "usr/bin/python3", "usr/bin/dpkg", "usr/bin/apt-get",
                  "usr/bin/git", "usr/bin/curl"):
        found = entry(probe)
        if found:
            execs.append((probe, found[1]))
    ok_exec = all(is_exec(m) for _, m in execs)
    out["tar:executables"] = {
        "ok": ok_exec,
        "detail": ", ".join(f"{n}({oct(m & 0o777)})" for n, m in execs),
    }

    loader_found = None
    for name, (typ, mode) in index.items():
        if name.endswith(meta.loaders[0]):
            loader_found = (name, mode)
            break
    if loader_found:
        out["tar:loader-exec"] = {"ok": is_exec(loader_found[1]),
                                  "detail": f"{loader_found[0]} {oct(loader_found[1] & 0o777)}"}
    else:
        out["tar:loader-exec"] = {"ok": False, "detail": "loader not found in archive"}

    # representative non-executable configuration/data files
    # (symlinks legitimately carry 0777; only regular files are judged)
    data_files = []
    for probe in ("etc/passwd", "etc/os-release", "usr/lib/os-release",
                  "etc/apt/sources.list"):
        found = entry(probe)
        if found and found[0] == tarfile.REGTYPE:
            data_files.append((probe, found[1]))
    ok_data = all(not is_exec(m) for _, m in data_files)
    out["tar:non-executables"] = {
        "ok": ok_data,
        "detail": ", ".join(f"{n}={oct(m & 0o777)}" for n, m in data_files),
    }

    # directories must be archive dirs, searchable by the owner
    dir_ok = True
    dir_details = []
    for probe in ("usr/bin", "etc", "usr", "tmp", "root", "var/lib/buster"):
        found = entry(probe)
        if found:
            typ, mode = found
            dir_ok = dir_ok and typ == tarfile.DIRTYPE and bool(mode & 0o100)
            dir_details.append(f"{probe}({oct(mode & 0o777)})")
    out["tar:directories"] = {"ok": dir_ok, "detail": ", ".join(dir_details)}

    # merged-/usr aliases must be archived as symlinks
    sym_ok = True
    for alias, target in (("bin", "usr/bin"), ("sbin", "usr/sbin"),
                          ("lib", "usr/lib")):
        found = entry(alias)
        if found:
            sym_ok = sym_ok and found[0] == tarfile.SYMTYPE
    out["tar:merged-usr-symlinks"] = {"ok": sym_ok,
                                      "detail": "bin/sbin/lib -> usr/..."}
    return out


def read_text(root: Rootfs, rel: str) -> str:
    try:
        with open(root._path(rel), "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def load_bytes(path: str) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return b""


def find_loader(root: Rootfs, meta) -> str | None:
    tops = [root._path("lib64"), root._path("lib"),
            root._path(meta.deb_lib_dir())]
    for top in tops:
        if not os.path.isdir(top):
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            dirnames.sort()
            filenames.sort()
            for name in filenames:
                if _is_loader_name(name, meta):
                    return os.path.join(dirpath, name)
    return None


def _is_loader_name(name: str, meta) -> bool:
    if name in meta.loaders:
        return True
    # libc installs the real loader (e.g. ld-2.36.so); the public name is a
    # symlink. Match the ``ld-<version>.so``/``ld-linux-*.so`` pattern.
    lowered = name.lower()
    if not lowered.startswith("ld-"):
        return False
    import re as _re
    return bool(_re.match(r"^ld-([a-z0-9._-]*-)?\d+[.\d]*\.so(\.\d+)?$", lowered))


def loader_names_in_artifact(tar_path: str, meta) -> list[str]:
    present = []
    if not tar_path:
        return present
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            base = os.path.basename(member.name.rstrip("/"))
            if base in meta.loaders:
                present.append(member.name)
    return present


def main(argv: list | None = None) -> int:
    args = parse_args(argv)
    try:
        result = build_arch(args.arch, distro=args.distro, mirror=args.mirror,
                            security_mirror=args.security_mirror, out_dir=args.out,
                            buster_source=args.buster_source, keep=args.keep,
                            limit=args.limit)
    except Exception as exc:  # noqa: BLE001
        log.error("build failed for %s: %s", args.arch, exc)
        return 2
    print(f"checks passed: {result['checks_passed']}/{result['checks_total']}")
    return 0 if result["checks_total"] == result["checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())