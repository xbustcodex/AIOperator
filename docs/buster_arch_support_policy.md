# Buster OS Architecture Support Policy

Buster OS is **one operating system and one source tree**. CPU architectures
are **release targets**, not separate Buster variants. Adding an architecture
in the future means adding and testing a build target in the architecture
registry — never forking Buster OS or maintaining another implementation.

## Support tiers

- **enabled** — the distribution pipeline produces a release artifact, and
  the artifact is **constructed and structurally verified** for this
  architecture (package closure, ELF class/machine, dynamic loader, dpkg
  database, Buster installation, filesystem identity). Runtime execution
  testing is reported separately and only when it has actually been
  performed (native or via emulation).
- **candidate** — Debian publishes packages and the full Buster base
  dependency closure resolves for this architecture, but the architecture is
  not yet release-enabled: it still needs an artifact build, structural
  verification and, where the environment permits, runtime execution testing.

## Enabled architectures

| Token   | Machine     | ELF machine | CI class | Dynamic loader            | Role |
|---------|-------------|-------------|----------|---------------------------|------|
| amd64   | x86_64      | 62          | 64-bit   | ld-linux-x86-64.so.2      | primary desktop/cloud target |
| arm64   | aarch64     | 183         | 64-bit   | ld-linux-aarch64.so.1     | primary phone/mobile target |

Both are built and structurally verified by the release pipeline; the exact
Debian packages, libraries and dynamic loader are resolved automatically from
the upstream archive for each architecture.

## Candidate architectures (closure-verified)

Debian (bookworm stable) publishes packages for these, and the Buster base
set (libc6, bash, coreutils, python3, git, curl, openssl, ssh, locales, …)
resolves for them. They are **not** release-enabled until they pass artifact
build + structural verification (+ runtime testing where possible):

- i386 (32-bit x86, EM_386, ld-linux.so.2)
- armhf (armv7l hard-float, EM_ARM, ld-linux-armhf.so.3)
- armel (32-bit ARM soft-float, EM_ARM, ld-linux.so.3)
- ppc64el (ppc64le, EM_PPC64, ld64.so.2)
- s390x (IBM Z, EM_S390, ld64.so.1)
- riscv64 (EM_RISCV, ld-linux-riscv64-lp64d.so.1) — does **not** resolve the
  full base closure on bookworm; re-evaluate when Debian provides a complete
  stable toolchain/image for it (e.g. trixie+).
- mips64el (EM_MIPS, mips64el-linux-gnuabi64)

Anonymous closure evaluation is run for every candidate during release
(`build_release.py --candidates-check`, result in
`dist/candidates-report.json`); it records resolvability, closure size, and
presence of libc6/python3/base set.

## Release output scheme

```
dist/
├── buster-os-<VERSION>-amd64-bookworm.tar.gz
├── buster-os-<VERSION>-arm64-bookworm.tar.gz
├── manifest-amd64.json
├── manifest-arm64.json
├── verification-amd64.json
├── verification-arm64.json
├── candidates-report.json  (closure evaluation of candidate archs)
├── release.json            (release matrix)
└── SHA256SUMS              (authoritative, all files)
```

## Enabling a new architecture

1. Add/extend the entry in `buster/osbuild/architectures.py` (Debian token,
   machine, ELF class/machine, triplet, dynamic loaders).
2. Run closure check: candidate must resolve the full base set.
3. Build the artifact and require a green structural verification for it.
4. Where possible, execute the artifact (native or emulated) and record
   `runtime_executed: true` in `verification-<arch>.json`.
5. Move the entry to `tier="enabled"` once solved.

An architecture is never claimed as supported merely because Debian
publishes packages for it; it must pass the Buster pipeline's own build and
validation gates.