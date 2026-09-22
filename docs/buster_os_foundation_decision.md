# Buster OS — Linux Foundation Decision

Buster OS is a complete, general-purpose Linux environment. The choice of
upstream foundation is a long-term architectural decision made independently
of any particular deployment target (TerminalP, Termux, VM, container, etc.).

## Requirements summary

- Mature general-purpose Linux environment that ordinary Linux software
  can run against without special adaptations.
- Large, stable package ecosystem with proven maintenance.
- ARM64/AArch64 **and** x86_64 primary architectures, extensible later.
- glibc (not musl) for broadest binary-compatibility with prebuilt AI/ML
  tooling, Python C extensions, desktop/GUI software, and third-party
  Linux applications.
- Modern Python available in official repositories.
- Quality apt/dpkg or equivalent package manager.
- Ability to maintain Buster/Prime Tech packages and repositories alongside
  upstream packages.
- Strong upstream security maintenance and LTS/stable cadence.
- Path toward public distribution (licensing, provenance, attribution).
- Reproducible rootfs construction from hosted archives.

## Candidates evaluated

| Criterion | Debian (stable) | Alpine | Arch | Fedora | Ubuntu LTS | Void |
|---|---|---|---|---|---|---|
| glibc base | Yes | No (musl) | Yes | Yes | Yes | No |
| Package ecosystem breadth | Very large | Moderate | Rolling large | Large | Very large | Moderate |
| ARM64 + x86_64 first-class | Yes | Yes | Yes | Yes | Yes | Yes |
| apt / dpkg ecosystem maturity | Excellent | N/A | pacman | dnf/rpm | apt | xbps |
| Upstream security maintenance cadence | Stable ~2yr (stable+LTS+ELTS) | Rolling + stable | Rolling | ~6mo + EOL | 5yr LTS + ESM | Rolling |
| Python + dev tooling | Native | Native | Native | Native | Native | Native |
| AI/ML prebuilt compatibility (glibc) | Strong | Weak | Strong | Strong | Strong | Weak |
| Future desktop/GUI software compatibility | Excellent | Moderate | Strong | Strong | Excellent | Limited |
| Reproducible rootfs construction | Standard debootstrap/apt | apk-tools-static | pacstrap | dnf/systemd-nspawn | debootstrap | xbps-install |
| Licensing/redistribution friendliness | Excellent | Good | Good | Good (CLs) | Good (CLA) | Good |
| Long-term upstream maintenance burden | Low (stable cadence, DPL, ELTS) | Low | Medium (rolling breakage) | Medium | Medium (ESM after LTS) | Medium |
| Ease of maintaining Buster packages alongside upstream | apt native | apk separate | pacman separate | rpm separate | apt native | xbps separate |

## Decision: Debian Stable (glibc, apt/dpkg ecosystem)

**Buster OS is built on Debian stable.**

Rationale:

1. **glibc binary compatibility.** Most prebuilt Linux AI/ML libraries, Python wheels with native extensions, and desktop applications target glibc. Musl-based systems (Alpine) require rebuilding most of this ecosystem; that is a significant long-term cost Buster can avoid.

2. **Very large, mature package base.** Debian stable provides tens of thousands of verified packages across server, development, desktop and embedded use-cases. Buster can use standard Linux software without recompilation or reimplementation.

3. **apt / dpkg maturity.** Debian's apt/dpkg ecosystem is battle-tested for upgrade safety, dependency resolution, pinning, security patching, and hosting custom repositories (e.g., reprepro). This is a strong foundation for Buster's own package layer.

4. **Stable release cadence.** Debian stable provides a reliable, security-maintained base with LTS/ELTS options, reducing churn and maintenance burden for a long-lived OS.

5. **glibc path for future GUI.** Desktop and GUI libraries (GTK, Qt, X11/Wayland, pipewire) are readily available on Debian. This keeps Buster's future GUI viable on Linux-native paths rather than requiring Android-hosted workarounds.

6. **Standard rootfs construction.** debootstrap/apt/apt-utils provide well-understood mechanisms for reproducible rootfs builds. The dpkg database, maintainer scripts and configuration management are well documented.

7. **Licensing and redistribution.** Debian is freely redistributable with proper attribution, clear provenance tracking and established practices for maintaining downstream packages alongside upstream.

## What Buster is not doing

Buster is not Debian. Buster uses Debian as an upstream Linux foundation and builds its own operating environment, identity, packages, configuration, services, and intelligence architecture on top of it. Buster's own functionality is delivered as Buster packages and system configuration, preserving upstream provenance while establishing an independently identifiable operating system.

## Supported architectures

Primary:
- amd64
- arm64/aarch64

Architecture-specific components (e.g., kernel binaries if/when added, prebuilt toolchains) are isolated so Buster's own packages can be architecture-independent where possible, enabling future expansion to other targets.

## Repository and reproducibility

Buster's rootfs build pins a specific Debian archive snapshot (date+mirror) and records all resolved package versions, filenames and checksums in a reproducible manifest. Rebuilding with the same manifest reconstructs the same userspace, independent of which exact mirror is used at that moment, provided the snapshot is archived.

Buster/Prime Tech packages live in a separate Buster repository layer coexisting with upstream Debian packages via apt pinning and distribution configuration. This enables standard Debian software to remain available while Buster packages take precedence for Buster-specific components.
