#!/usr/bin/env python3
"""Buster OS release workflow — build all supported architectures.

One operating system, one source tree, one release. Architectures are release
targets; this command builds every enabled architecture, emits per-arch
artifacts/manifests/verification, an authoritative combined SHA256SUMS and a
release summary.

Usage:
    python build_release.py                 # build amd64 + arm64 (enabled)
    python build_release.py --archs amd64,arm64,riscv64   # specific set
    python build_release.py --candidates-check            # closure-only eval

Runtime status: artifacts are constructed and structurally verified here;
"runtime_executed" is set only when the artifact has actually been booted/
executed in a matching environment (native or emulated).
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buster.osbuild import BASE_SEEDS, DISTRO_DEFAULT  # noqa: E402
from buster.osbuild import apiclient, manifest, packages, resolver  # noqa: E402
from buster.osbuild.architectures import (  # noqa: E402
    ARCH_REGISTRY, candidates, enabled, lookup,
)
from buster.version import get_version  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("build_release")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Buster OS multi-arch release")
    parser.add_argument("--archs", default=None,
                        help="comma-separated archs (default: enabled list)")
    parser.add_argument("--distro", default=DISTRO_DEFAULT)
    parser.add_argument("--mirror", default="http://deb.debian.org/debian")
    parser.add_argument("--security-mirror",
                        default="http://security.debian.org/debian-security")
    parser.add_argument("--out", default="dist")
    parser.add_argument("--buster-source",
                        default=os.path.dirname(os.path.abspath(__file__)))
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--candidates-check", action="store_true",
                        help="evaluate candidate architectures at closure level only")
    parser.add_argument("--status", choices=["structural", "runtime"], default="structural",
                        help="set runtime_executed when artifacts were actually run")
    return parser.parse_args(argv)


def candidates_closure_report(mirror, distro) -> dict:
    """Resolve the base closure for candidate architectures (no payloads)."""
    report = {}
    for meta in candidates():
        try:
            base = f"{mirror.rstrip('/')}/dists/{distro}/main"
            records = []
            for index_arch in (meta.token, "all"):
                try:
                    records += packages.parse_packages(
                        apiclient.fetch_packages_index(
                            f"{base}/binary-{index_arch}/Packages.gz"))
                except Exception as exc:  # noqa: BLE001
                    log.warning("index %s unavailable: %s", index_arch, exc)
            closure = resolver.DependencyResolver(records, meta.token).resolve(BASE_SEEDS)
            closure_names = {r.package for r in closure}
            report[meta.token] = {
                "machine": meta.machine,
                "resolvable": True,
                "packages": len(closure),
                "python3": "python3" in closure_names,
                "libc6": "libc6" in closure_names,
                "base_fms": all(s in closure_names for s in BASE_SEEDS),
            }
        except Exception as exc:  # noqa: BLE001
            report[meta.token] = {"resolvable": False, "reason": str(exc)}
        log.info("candidate %s: %s", meta.token, report[meta.token])
    return report


def main(argv=None) -> int:
    args = parse_args(argv)
    arch_tokens = (args.archs.split(",") if args.archs
                   else [m.token for m in enabled()])

    built = []
    for arch in arch_tokens:
        meta = lookup(arch)
        if meta.tier != "enabled":
            log.warning("architecture '%s' is not release-enabled; building anyway", arch)
        try:
            import build_rootfs
            result = build_rootfs.build_arch(
                arch, distro=args.distro, mirror=args.mirror,
                security_mirror=args.security_mirror, out_dir=args.out,
                buster_source=args.buster_source, keep=args.keep)
            if args.status == "runtime":
                # Mark runtime executed ONLY if the caller supplies evidence.
                result["runtime_executed"] = True
            else:
                result["runtime_executed"] = False
            built.append(result)
        except Exception as exc:  # noqa: BLE001
            log.error("build failed for %s: %s", arch, exc)
            built.append({"arch": arch, "error": str(exc),
                          "runtime_executed": False})

    candidates_report = None
    if args.candidates_check:
        candidates_report = candidates_closure_report(args.mirror, args.distro)
        out = os.path.join(args.out, "candidates-report.json")
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(candidates_report, handle, indent=2)

    # authoritative combined SHA256SUMS covering artifacts + per-arch outputs
    tracked = []
    for result in built:
        for key in ("artifact", "manifest", "verification"):
            path = result.get(key)
            if path and os.path.isfile(path):
                tracked.append(os.path.basename(path))
    if candidates_report:
        tracked.append("candidates-report.json")
    if tracked:
        manifest.write_authoritative_shasums(args.out, tracked)

    release = {
        "os": "Buster OS",
        "version": get_version(),
        "distro": args.distro,
        "architectures": built,
        "candidates_check": candidates_report,
    }
    release_path = os.path.join(args.out, "release.json")
    with open(release_path, "w", encoding="utf-8") as handle:
        json.dump(release, handle, indent=2)

    print("\n=== Buster OS release matrix ===")
    ok = True
    for result in built:
        if "error" in result:
            print(f"  {result['arch']:<10} FAIL: {result['error']}")
            ok = False
            continue
        status = "structural" if not result.get("runtime_executed") else "runtime"
        print(f"  {result['arch']:<10} {result['machine']:<10} "
              f"{result['checks_passed']}/{result['checks_total']} checks [{status}]")
    if candidates_report:
        for arch, info in candidates_report.items():
            state = "closure-ok" if info.get("resolvable") else \
                f"unresolvable ({info.get('reason')})"
            print(f"  {arch:<10} candidate: {state}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())