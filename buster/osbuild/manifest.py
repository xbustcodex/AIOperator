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


def write_manifest_and_checksums(out_dir: str, manifest: dict,
                                name: str | None = None) -> dict:
    """Write a manifest (per-arch by default) and append to SHA256SUMS."""
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = name or os.path.join(out_dir, "manifest.json")
    manifest.pop("manifest_sha256", None)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    manifest["manifest_sha256"] = sha256_file(manifest_path)

    sums_lines = [
        f"{manifest['artifact_sha256']}  {manifest['artifact_file']}",
        f"{manifest['manifest_sha256']}  {os.path.basename(manifest_path)}",
    ]
    _append_shasums(os.path.join(out_dir, "SHA256SUMS"), sums_lines)
    return manifest


def _append_shasums(path: str, lines: list[str]) -> None:
    existing = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    entries = {}
    for line in (existing + "\n" + "\n".join(lines)).splitlines():
        if line.strip():
            digest, _, fname = line.partition("  ")
            entries[fname.strip()] = digest.strip()
    with open(path, "w", encoding="utf-8") as handle:
        for fname in sorted(entries):
            handle.write(f"{entries[fname]}  {fname}\n")


def write_authoritative_shasums(out_dir: str, files: list[str]) -> str:
    """Rewrite SHA256SUMS to cover exactly the given files, sorted."""
    entries = {}
    for name in sorted(files):
        digest = sha256_file(os.path.join(out_dir, name))
        entries[name] = digest
    path = os.path.join(out_dir, "SHA256SUMS")
    with open(path, "w", encoding="utf-8") as handle:
        for fname in sorted(entries):
            handle.write(f"{entries[fname]}  {fname}\n")
    return path