"""Manifests and checksums for Buster OS distribution artifacts."""

import hashlib
import json
import os
from typing import Iterable


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(*, version: str, arch: str, distro: str,
                   distro_release: str, mirror: str, snapshot_date: str,
                   buster_commit: str = "", packages: Iterable[dict],
                   artifact_name: str, artifact_sha256: str) -> dict:
    return {
        "artifact": "Buster OS Linux distribution rootfs",
        "os": "Buster OS",
        "version": version,
        "architecture": arch,
        "foundation": distro,
        "distro_release": distro_release,
        "mirror": mirror,
        "snapshot_date": snapshot_date,
        "buster_commit": buster_commit,
        "artifact_file": artifact_name,
        "artifact_sha256": artifact_sha256,
        "packages": sorted(packages, key=lambda p: p["name"]),
        "package_count": len(tuple(packages)),
    }


def write_manifest_and_checksums(out_dir: str, manifest: dict) -> dict:
    """Persist manifest.json + SHA256SUMS for all artifact files."""
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    manifest["manifest_sha256"] = sha256_file(manifest_path)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    sums_lines = [
        f"{manifest['artifact_sha256']}  {manifest['artifact_file']}",
        f"{manifest['manifest_sha256']}  manifest.json",
    ]
    with open(os.path.join(out_dir, "SHA256SUMS"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(sums_lines) + "\n")
    return manifest