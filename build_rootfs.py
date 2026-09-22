#!/usr/bin/env python3
"""Buster OS Linux distribution builder.

Reproducibly constructs a populated Buster OS root filesystem from the
upstream Linux foundation (Debian bookworm), installs the Buster system
layer and the existing Buster runtime, and packages the result as a
deployable distribution/rootfs artifact with manifests and checksums.

Usage:
    python build_rootfs.py [--arch amd64|arm64] [--distro bookworm]
                           [--mirror URL] [--security-mirror URL]
                           [--out dist] [--buster-source .] [--keep]

The build is network-backed: it downloads package indexes and .deb archives
from the selected Debian archive. The resulting rootfs is configured fully at
first boot by dpkg (maintainer scripts/configuration), which is the standard
debootstrap model.
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import shutil
import sys
import tarfile
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buster.osbuild import BASE_SEEDS, DISTRO_DEFAULT, autodetect_arch  # noqa: E402
from buster.osbuild import apiclient, deb, manifest, packages, resolver  # noqa: E402
from buster.osbuild.rootfs import Rootfs  # noqa: E402
from buster.version import get_version  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("build_rootfs")


def parse_args(argv: list | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Buster OS rootfs builder")
    parser.add_argument("--arch", default=None, help="target architecture")
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
            indexes[index_arch] = packages.parse_packages(apiclient.fetch_packages_index(url + ".gz"))
            log.info("index %s: %d packages", index_arch, len(indexes[index_arch]))
        except Exception as exc:  # noqa: BLE001
            log.warning("index %s unavailable: %s", index_arch, exc)
    return indexes


def build_artifact(rootfs_dir, root, arch, version, out_dir, distro):
    os.makedirs(out_dir, exist_ok=True)
    artifact_name = f"buster-os-{version}-{arch}-{distro}.tar.gz"
    artifact_path = os.path.join(out_dir, artifact_name)
    if os.path.isfile(artifact_path):
        os.remove(artifact_path)
    with tarfile.open(artifact_path, "w:gz") as tar:
        tar.add(rootfs_dir, arcname=".")
        root.pack_extra_members(tar)
    return artifact_name, artifact_path


def verify_rootfs(root: Rootfs, artifact_path: str | None = None) -> dict:
    checks = {}
    required = [
        "etc/os-release", "etc/passwd", "etc/group", "etc/shadow",
        "etc/nsswitch.conf", "etc/hosts", "etc/fstab", "etc/apt/sources.list",
        "usr/bin/dpkg", "usr/bin/apt-get", "var/lib/dpkg/status",
        "usr/lib/os-release", "opt/buster/lib/buster/version.py",
        "home/buster", "var/lib/buster", "run/buster", "tmp", "dev", "proc",
        "sys", "root", "bin", "sbin", "lib",
    ]
    for path in required:
        checks[f"exists:{path}"] = os.path.exists(root._path(path))

    # merged-/usr: a binary may live under /usr/bin or under /bin (via the
    # /usr merge), and python3 is normally an alternatives symlink.
    def binary_present(name: str) -> bool:
        for rel in (f"usr/bin/{name}", f"bin/{name}", f"usr/bin/{name}3"):
            if os.path.isfile(root._path(rel)):
                return True
        if artifact_path:
            with tarfile.open(artifact_path, "r:gz") as tar:
                names = {m.name for m in tar.getmembers()}
                if any(n in names for n in (f"usr/bin/{name}", f"bin/{name}")):
                    return True
        return False

    checks["binary:bash"] = binary_present("bash")
    checks["binary:python3"] = binary_present("python3")
    checks["binary:git"] = binary_present("git")
    checks["binary:curl"] = binary_present("curl")

    with open(root._path("etc/os-release"), encoding="utf-8") as fh:
        osrelease = fh.read()
    checks["identity:busteros"] = 'ID=busteros' in osrelease
    checks["identity:ID_LIKE-debian"] = 'ID_LIKE' in osrelease
    with open(root._path("var/lib/dpkg/status"), encoding="utf-8") as fh:
        status = fh.read()
    checks["packages:coreutils"] = "Package: coreutils" in status
    checks["packages:python3"] = "Package: python3" in status
    checks["packages:git"] = "Package: git" in status
    return checks


def main(argv: list | None = None) -> int:
    args = parse_args(argv)
    arch = args.arch or autodetect_arch()
    version = get_version()
    distro = args.distro
    mirror = args.mirror
    security_mirror = args.security_mirror
    snapshot_date = datetime.date.today().isoformat()

    workdir = tempfile.mkdtemp(prefix="buster-rootfs-")
    rootfs_dir = os.path.join(workdir, "rootfs")
    root = Rootfs(rootfs_dir, arch)

    log.info("Buster OS %s distribution build (arch=%s foundation=%s)",
             version, arch, distro)
    root.build_layout()
    indexes = fetch_index(mirror, arch, distro)
    records = [r for idx in indexes.values() for r in idx]
    if not records:
        log.error("no package index available from %s", mirror)
        return 2

    depresolver = resolver.DependencyResolver(records, arch)
    try:
        selected = depresolver.resolve(list(BASE_SEEDS))
    except KeyError as exc:
        log.error("dependency resolution failed: %s", exc)
        return 2
    log.info("resolved %d packages from base seeds", len(selected))

    contents: dict[str, deb.DebContent] = {}
    package_manifest = []
    mirror_base = mirror.rstrip("/")
    used_records = selected[: args.limit] if args.limit else selected
    for num, record in enumerate(used_records, 1):
        filename = record.filename
        if not filename:
            continue
        url = f"{mirror_base}/{filename.lstrip('/')}"
        log.info("[%d/%d] %s %s", num, len(selected), record.package, record.version)
        raw = apiclient.fetch_bytes(url, timeout=60)
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
    root.install_buster(args.buster_source, version)

    # package the artifact
    artifact_name, artifact_path = build_artifact(rootfs_dir, root, arch, version,
                                                  args.out, distro)
    checks = verify_rootfs(root, artifact_path)
    log.info("rootfs verification: %d/%d checks passed",
             sum(1 for v in checks.values() if v), len(checks))

    manifest_data = manifest.build_manifest(
        version=version, arch=arch, distro="debian", distro_release=distro,
        mirror=mirror, snapshot_date=snapshot_date,
        artifact_name=artifact_name,
        artifact_sha256=manifest.sha256_file(artifact_path),
        packages=package_manifest)
    manifest.write_manifest_and_checksums(args.out, manifest_data)

    report_path = os.path.join(args.out, "verification.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump({"checks": checks, "manifest": os.path.basename(args.out) + "/manifest.json"},
                  handle, indent=2)

    if args.keep:
        print(f"rootfs workdir kept at {rootfs_dir}")
    else:
        shutil.rmtree(workdir, ignore_errors=True)

    print(f"\nBuster OS {version} rootfs artifact: {os.path.join(args.out, artifact_name)}")
    print(f"verification: {sum(1 for v in checks.values() if v)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())