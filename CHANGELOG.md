# Changelog

All notable changes to Buster OS are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [0.4.0] - 2026-09-24

### Added — first consumer-facing Buster UI

- **Local web frontend with a server-side JSON API** (`buster/gui/`): the GUI
  is a pure client of the Buster daemon over the existing RemoteKernel/RPC
  boundary. The GUI process never constructs or imports a Kernel,
  EventRouter, Scheduler, memory authority or agent system (verified by
  tests); the daemon keeps running independently of the UI.
- **Design system**: near-black/purple premium visual language, mobile-first
  responsive layout that scales to desktop, reduced-motion support,
  touch-friendly targets, focus rings, and screen-reader labels.
- **Purple orb as the centrepiece** (reusable `orb.js` state model + CSS
  renderer): idle, listening, thinking, working, speaking, needs attention,
  offline/local and error states, with deliberate motion and
  `prefers-reduced-motion` handling. Header-orb = small persistent; Home =
  large dominant; Live = hero size.
- **Home**: answers "is Buster available / what is it doing / anything
  waiting / recent activity / what can I ask" with real runtime state.
- **Conversation (Talk)**: real round-trips through the daemon
  (`/api/chat` → `process_goal`), history stored in Buster's memory store
  (no second conversation authority), error/offline handling.
- **Live/voice**: hero orb bound to interaction state; portable
  `AudioBackend` interface with a browser implementation, graceful fallback
  to text when the platform provides none.
- **Everyday areas**: Files (through the capability/permission gate),
  Tasks & Projects (goals in plain language), Memory & Preferences,
  Permissions & approvals, Device, Activity, Settings, Updates, plus a
  separate **Advanced** technical area (health, providers, goals, world
  model, memory, capabilities, jobs, audit via `intel` views).
- **Onboarding**: first-run flow that sets consumer preferences, confirms
  runtime availability and leads to Home without touching Linux internals.
- **Offline/local operation**: the UI stays useful locally and distinguishes
  "offline/local" from errors; external-provider loss never reads as loss of
  Buster itself.
- **Frontend RPC ops** added to the existing runtime authority (`activity`,
  `permissions_list`, `update_info`) plus `buster-gui` launcher and web
  assets shipped in the rootfs (`/usr/share/buster-gui`).
- **Tests**: Node-based frontend logic tests (orb transitions, nav, state)
  and Python GUI integration tests that drive a real runtime over HTTP and
  assert real state (plus no-Kernel-in-GUI verification). Full suite: 190
  tests passing.

## [0.3.2] - 2026-09-22

### Fixed — release-blocking rootfs permissions defect

First ARM64 deployment exposed executables recorded in release archives as
mode 0666 (PRoot: `/bin/bash is not executable`). Root cause: the artifact
tar was serialized from staging-filesystem ``stat`` data, and staging hosts
that cannot represent Unix modes report them as 0666.

- **Authoritative metadata overlay** (`buster/osbuild/rootfs.py`): file type,
  Unix mode and link target are captured directly from each ``.deb`` payload
  member (and from Buster's own writers) during extraction; the release
  tarball is now serialized entirely from that overlay via
  ``Rootfs.pack_tree``, never from staging-tree stat calls.
- **Merged-/usr handled in the overlay**: package payload paths are normalized
  to the ``/usr`` layout at extraction (content + metadata), and ``bin``/
  ``sbin``/``lib``(``/lib64``) are archived as symlinks regardless of whether
  the build host can create symlinks.
- Hard-linked and symbolic data.tar members are preserved in the archive;
  payload bytes that a build host cannot write to disk (e.g. Windows-invalid
  names) are emitted verbatim with their true Unix names and modes.
- **Archived-metadata verification added** (`build_rootfs.py`): the produced
  tarball is inspected directly for executable modes on critical executables
  and dynamic loaders, non-executable modes on representative configuration/
  data files, directory search bits (including 0700 `/root`, 1777 `/tmp`),
  and merged-/usr symlinks — so a broken-permission artifact cannot pass.
- **Regression tests** (`buster/tests/test_osbuild.py` FileModePreservation,
  extended `buster/tests/test_multirarch.py`): prove package modes survive
  ``.deb`` extraction → staging → final release tarball and that the fix does
  not make everything executable.
- amd64 and arm64 release artifacts rebuilt and re-verified.

### Changed
- Version 0.3.2.

## [0.3.1] - 2026-09-22

### Added — multi-architecture release pipeline

- **Architecture registry** (`buster/osbuild/architectures.py`): centralized
  Debian tokens, machines, ELF class/machine, multiarch triplets and dynamic
  loaders for amd64/arm64 (enabled) and i386, armhf, armel, ppc64el, s390x,
  riscv64, mips64el (candidate). One OS, one source tree; architectures are
  release targets.
- **Generalized builder** (`build_rootfs.py`, `buster/osbuild/*`): no hidden
  amd64 assumptions; per-architecture package resolution, dynamic-loader
  handling, manifest/verification/artifact naming.
- **Architecture-aware verification**: ELF class/machine parsing
  (`buster/osbuild/elf.py`) of the dynamic loader and core binaries, dpkg
  database architecture, package closure, Buster installation and filesystem
  identity. Distinguishes constructed+structural verification from
  actually-executed runtime testing (`runtime_executed` flag).
- **Single release workflow** (`build_release.py`): builds all enabled
  architectures, emits `buster-os-<v>-<arch>-bookworm.tar.gz`,
  `manifest-<arch>.json`, `verification-<arch>.json`, an authoritative
  combined `SHA256SUMS`, `release.json` and `candidates-report.json`
  (closure evaluation of candidate architectures).
- **Architecture support policy** documented (`docs/buster_arch_support_policy.md`).
- Multi-architecture offline test suite (`buster/tests/test_multirarch.py`).

### Changed
- Version 0.3.1. Distribution artifacts and manifests now carry per-arch
  names.

## [0.3.0] - 2026-09-22

### Added — Buster OS complete Linux environment

- **Linux foundation decision** (`docs/buster_os_foundation_decision.md`):
  candidates evaluated (Debian, Alpine, Arch, Fedora, Ubuntu, Void); Debian
  stable (bookworm, glibc, apt/dpkg) chosen as the long-term upstream
  foundation. ARM64/aarch64 and x86_64/amd64 first-class.
- **Rootfs distribution build** (`buster/osbuild/` + `build_rootfs.py`):
  reproducible, populated Buster OS rootfs constructed from the Debian
  archive — stdlib-only dpkg-index parser, .deb (ar/tar) extractor,
  dependency-closure resolver, merged-/usr rootfs layout, dpkg status
  database, base users/groups and system configuration, Buster identity
  (`/etc/os-release` → `ID=busteros`), manifests and checksums.
- **Buster system layer**: `/etc/buster` config, `/var/lib/buster`
  persistent state, `/var/log/buster` logs, `/opt/buster` runtime
  components, `/run/buster` runtime state, `busterctl`, systemd unit and
  sysvinit script, Python `.pth` wiring, logrotate, environment/profile.
- **Migration** from the v0.2.0 `~/.buster` application layout to the
  system layout (`buster/osbuild/migrate.py`) preserving memories,
  knowledge, experience, goals, plans, suggestions and configuration seeds
  — idempotent, with an identity marker.
- **Linux-environment diagnostics** (`run_os_doctor`): os-release identity,
  rootfs layout, dpkg package database, required packages, binaries,
  machine info.
- **`busterctl`** system control tool reusing the single-Kernel CLI.

### Changed

- Version 0.3.0. AGENTS.md, README and architecture docs updated to
  establish Buster OS as its own general-purpose Linux environment with
  TerminalP as one deployment mechanism (not the definition of Buster OS).
- Buster Runtime Kernel explicitly distinguished from the conventional
  Linux kernel throughout documentation.

### Tests

- `test_osbuild.py` (offline): version comparison, dependency parsing/
  resolution, .deb extraction, rootfs layout/merged-usr, dpkg status
  generation, Buster identity + system-layer install, manifests/checksums,
  v0.2.0 migration, OS doctor.

## [0.2.0] - 2026-09-22

### Added — intelligent Buster phone node
The foundation (kernel, single daemon, RPC, capabilities, permissions, audit,
PlannerAgent, reflection, experience, TerminalP) is extended in place into one
coherent cognitive system without introducing a second runtime.

- **Basal nervous system** (`intelligence/nervous.py`): heartbeat, node
  health, idle/activity/sleep detection, battery/charging/thermal, CPU,
  memory, storage, network, capability, provider, job and host signals.
  Converts raw sensor data into normalized, deduplicated signals; no LLM.
- **Cognitive rhythm** (`intelligence/rhythm.py`): deterministic state machine
  (active, background, idle, reflection, maintenance, constrained, degraded,
  recovery, sleep) that gates expensive cognition.
- **Attention** (`intelligence/attention.py`): scores signals by relevance,
  urgency, novelty, goals and rhythm; suppresses routine noise.
- **World model** expansion (`kernel/world_model.py`): observed vs inferred
  facts with provenance/confidence, entities, and a bounded event history.
- **Memory architecture** (`intelligence/memory.py`): working, episodic and
  procedural memory plus a MemoryCoordinator for ranked retrieval,
  consolidation, contradiction detection, TTL expiry and diagnostics.
- **Learning** (`intelligence/learning.py`): context→intention→plan→action→
  result→evaluation→lesson cycles; capability reliability tracking;
  procedural recipe reliability. Learning never grants authority.
- **Reflection** (`intelligence/reflection.py`): bounded, trigger-driven
  passes producing lessons, hypotheses and unresolved questions.
- **Curiosity** (`intelligence/curiosity.py`): prioritized knowledge-gap
  questions (repeated failures, stalled goals, unused capabilities).
- **Goals** (`intelligence/goals.py`): persisted goal registry (not a
  scheduler) with priorities, dependencies, status, progress, provenance.
- **Plans** (`intelligence/plans.py`): persisted structured plans with
  capability-based steps, replanning and step outcomes.
- **Agent roles** (`intelligence/agents.py`): planner/researcher/builder/
  tester/reviewer/fixer/observer/memory-worker/maintenance-worker over ONE
  shared PlannerAgent architecture with capability-prefix constraints.
- **Cognitive orchestration** (`intelligence/orchestration.py`): an
  event-driven, scheduler-backed loop (sense→attend→world→memory→goals→plan→
  act→observe→learn→reflect) with bounded, resource-aware ticks.
- **Proactive intelligence** (`intelligence/proactive.py`): structured,
  non-executing suggestions (recurring failures, resources, unfinished goals,
  maintenance opportunities, connectivity recovery).
- **Self-maintenance** (`intelligence/maintenance.py`): diagnostics across
  runtime/config/memory/capabilities/providers/scheduler/RPC/audit/TerminalP
  plus bounded recovery.
- **Provider intelligence** (`intelligence/providers.py`): local-first health
  and selection; graceful degradation without cloud inference.
- **Observability**: `intel <section>` (nervous, rhythm, attention, world,
  memory, goals, plans, providers, curiosity, reflection, suggestions,
  agents, health) via shell, CLI and RPC; `goal`, `reflect`, `consolidate`,
  `health` shell/CLI commands and RPC ops.
- **Tests**: 132 passing, including `test_intelligence.py` (signals, rhythm,
  attention, memory, learning, reflection, curiosity, goals, plans, roles,
  proactive, maintenance, providers) and `test_cognitive_loop.py` (full loop,
  permission boundaries, restart persistence/no-duplicates, offline provider
  degradation, RPC access).

### Changed
- Version 0.2.0. World-model snapshot now includes observed/inferred facts,
  entities and a bounded event history while retaining the existing keys.

## [0.1.1] - 2026-09-22

### Changed
- **TerminalP is now the first-class phone host** for Buster OS. Host
  detection (`host_identity`) recognizes TerminalP prefixes and the
  `TERMINALP_VERSION` marker, and reports host identity wherever device
  facts are surfaced (doctor, installer, perception, `android.info`).
- Installer and doctor no longer refuse or fail on TerminalP: any Termux-class
  Android terminal (`/data/data/.../files/usr`, TerminalP or Termux markers)
  is accepted as a valid host.
- Host API bridge prefers the `terminalp-api` binary and falls back to
  `termux-api` for compatibility; capabilities and sensors report the
  detected binary name.
- Documentation and CLI banner updated to describe TerminalP as the Buster
  OS phone host; Termux-class compatibility preserved.

### Added
- Host-detection acceptance tests (`test_host.py`): TerminalP prefix / env
  marker detection, generic Android terminal acceptance, doctor and
  installer acceptance.

## [0.1.0] - 2026-09-20

### Added
- Package skeleton with version, configuration, and logging subsystems.
- Kernel core with lifecycle control (`start` / `stop` / `status`) wiring
  capabilities, AI, memory, security and perception.
- Central event bus (`EventRouter`) with sync/async dispatch.
- Priority scheduler with one-shot, periodic and cancellable jobs supporting
  job control from the shell and CLI.
- Permission gate with grant/deny rules and deny-by-default behavior.
- Versioned world model and component state registry.
- Agent manager and agent interface.
- Append-only JSON-lines audit trail.

### Capability system
- Registry dispatch pipeline: ExecutionContext -> event lifecycle ->
  permission + elevation gate -> invoke -> audit.
- `capability.calling` / `capability.succeeded` / `capability.failed` events.
- Compatibility adapters: `FunctionCapability` and `LegacyRouterAdapter`.

### Core capabilities
- Filesystem (`fs.list/read/write/mkdir/delete/stat/exists/touch`) with
  delete protection.
- Shell (`shell.run` / `shell.check`) and terminal (`terminal.open` /
  `write` / `close` / `run`).
- Python runner (`python.eval` / `python.exec`) with a jailed namespace.
- Git (`git.status/log/branch/clone/add/commit/pull`).
- Android/TerminalP (`android.info` / `battery` / `sensors`; TerminalP-first,
  Termux-class compatible).
- Process/system (`process.list` / `process.kill` / `system.info`).
- Networking (`net.get` / `net.post` / `net.dns` / `net.ping`) via stdlib.

### AI
- Provider registry with named lookups and defaults.
- `LocalProvider` on-device deterministic engine (pluggable).
- `RemoteProvider` OpenAI-compatible HTTP client (stdlib only).
- `AgentOrchestrator`: goal -> plan -> bounded capability execution loop,
  feeding outcomes into experience memory.

### Memory
- Persistent key/value store with TTL.
- ExperienceMemory append-only log.
- KnowledgeMemory learned facts with confidence and provenance.
- ReflectionEngine hooks distilling experiences into knowledge.

### Perception
- Sensor abstraction (`Sensor`, `SensorHub`) with `DeviceSensor` and
  `EnvironmentSensor`; extensible to future sensors.

### Security
- ExecutionContext / SecurityContext propagation.
- Delete protection for install, config, memory, log and state trees.
- ElevationManager gating sensitive actions (deny by default).

### Shell
- Quote-aware command parser with `--option` support.
- Command registry and structured results.
- Interactive REPL: kernel dispatch, capability invocation (`run`), job
  control (`jobs`), permissions (`grant`/`deny`), memory (`mem`), audit.

### CLI
- `start`, `status`, `doctor`, `version`, `shell`.
- Management: `caps`, `run`, `grant`, `deny`, `config`, `jobs`, `audit`.

### Engineering
- Idempotent installer and kernel launcher.
- Offline bootstrap (`bootstrap.py` / `buster bootstrap`) that never boots a
  kernel; runtime seeds applied by the daemon at `start`.
- Single-runtime lifecycle CLI: `bootstrap` -> `start` -> `status` -> `shell`
  -> `stop`, guarded by an atomic PID + heartbeat lock that refuses a second
  runtime and is released on clean shutdown.
- Runtime daemon with a deterministic file-based JSON request/response
  transport (`install/state/rpc/`), verified by `check_runtime.py`
  (lock semantics, full op surface, cross-process boot cycle).
- Windows-safe process-liveness probe (ctypes `OpenProcess` instead of
  `os.kill(pid, 0)`, which hangs/fails unpredictably on Store builds).
- Build script (`build.py`): compile check, full test suite, CLI smoke test,
  runtime check, clean distribution packaging under `dist/`.
- Documentation (`architecture.md`, README usage and lifecycle guide).
- Test suite: config, event router, kernel, scheduler, permissions, audit,
  capabilities (registry/adapters/impl), memory, security, AI, perception,
  shell parser/session, orchestration, bootstrap, runtime, and end-to-end
  integration.