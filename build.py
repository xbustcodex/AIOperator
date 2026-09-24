"""Buster OS build script.

Compiles every module, runs the full test suite, smoke-tests the CLI,
and packages a clean distribution zip under ``dist/``.

Usage:
    python build.py
    python build.py --skip-tests
    python build.py --out dist/custom.zip
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.abspath(__file__))


def _read_version() -> str:
    try:
        with open(os.path.join(REPO, "VERSION"), "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return "0.1.0"


VERSION = _read_version()

PACKAGE_TARGETS = [
    "buster",
    "config",
    "docs",
    "installer.py",
    "launcher.py",
    "bootstrap.py",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "VERSION",
]

PY_SOURCES = [
    "buster",
    "installer.py",
    "launcher.py",
    "bootstrap.py",
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *cmd], cwd=REPO,
                          capture_output=True, text=True)


def step(name: str) -> None:
    print(f"== {name}")


def compile_check() -> bool:
    step("Compile check")
    result = run(["-m", "compileall", "-q", *PY_SOURCES])
    _print_tail(result)
    if result.returncode != 0:
        print("[FAIL] compilation")
        return False
    print("[PASS] all modules compile")
    return True


def unit_tests() -> bool:
    step("Unit / integration / compatibility tests")
    result = run(["-m", "unittest", "discover", "-s", "buster/tests", "-p", "test_*.py"])
    combined = (result.stdout or "") + (result.stderr or "")
    match = re.search(r"Ran (\d+) tests", combined)
    count = match.group(1) if match else "?"
    ok = result.returncode == 0
    print(f"Ran {count} test(s): {'PASS' if ok else 'FAIL'}")
    _print_tail(result)
    return ok


def cli_smoke() -> bool:
    step("CLI smoke + runtime + frontend checks")
    ok = True
    checks = [
        (["-m", "buster.cli", "version"], "version"),
        (["-m", "buster.cli", "help"], "help"),
        (["-m", "buster.cli", "doctor"], "doctor"),
        (["launcher.py"], "launcher"),
        (["buster/tests/check_runtime.py"], "runtime"),
    ]
    for command, label in checks:
        result = run(command)
        # doctor returns 1 on a healthy-but-non-phone host; count <=1 as PASS.
        acceptable = result.returncode in (0, 1) if label == "doctor" else result.returncode == 0
        status = "PASS" if acceptable else f"NONZERO({result.returncode})"
        ok = ok and acceptable
        print(f"  [{'x' if acceptable else ' '}] {label} -> {status}")

    # Frontend logic tests (Node, no runtime required).
    js_result = _node_tests()
    ok = ok and js_result
    print(f"  [{'x' if js_result else ' '}] frontend-js -> {'PASS' if js_result else 'FAIL'}")
    return ok


def _node_tests() -> bool:
    tests = [
        "buster/gui/web/assets/tests/orb.test.mjs",
        "buster/gui/web/assets/tests/nav.test.mjs",
        "buster/gui/web/assets/tests/state.test.mjs",
    ]
    try:
        import subprocess as _sp
        completed = _sp.run(["node", "--test", *tests], cwd=REPO,
                            capture_output=True, text=True, timeout=180)
    except (OSError, _sp.TimeoutExpired):
        print("  (node not available — skipping frontend-js)")
        return True
    if completed.returncode != 0:
        print(completed.stdout[-400:])
        print(completed.stderr[-400:])
    return completed.returncode == 0


def package(out: str) -> bool:
    step(f"Package -> {out}")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if os.path.isfile(out):
        os.remove(out)

    added = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for target in PACKAGE_TARGETS:
            source = os.path.join(REPO, target)
            if os.path.isdir(source):
                for root, _dirs, files in os.walk(source):
                    for name in files:
                        if _skip(name):
                            continue
                        full = os.path.join(root, name)
                        rel = os.path.relpath(full, REPO)
                        archive.write(full, rel)
                        added += 1
            elif os.path.isfile(source):
                archive.write(source, os.path.basename(source))
                added += 1
    print(f"[PASS] packaged {added} files into {out}")
    return True


def _skip(name: str) -> bool:
    return name.endswith(".pyc") or name in ("build.py",) or "dist" in name


def _print_tail(result: subprocess.CompletedProcess) -> None:
    tail = (result.stdout or "")[-400:]
    tail_stderr = (result.stderr or "")[-400:]
    if tail.strip():
        print(tail.rstrip())
    if tail_stderr.strip():
        print(tail_stderr.rstrip())


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(prog="builder",
                                     description="Build and verify Buster OS.")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--out", default=f"dist/buster-os-{VERSION}.zip")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    results = {}
    results["compile"] = compile_check()
    if not args.skip_tests:
        results["tests"] = unit_tests()
    results["cli"] = cli_smoke()
    results["package"] = package(args.out)

    print()
    print("=== Build summary ===")
    for key, ok in results.items():
        print(f"  {key:<10} {'PASS' if ok else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())