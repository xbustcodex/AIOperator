# Buster OS Architecture

Buster OS is its own complete, general-purpose Linux environment for
**TerminalP on Android** and other suitable hosts, built on a proven upstream
Linux foundation (Debian stable). It has its own root filesystem, userspace,
configuration, package environment, identity, build process and deployable
rootfs artifact.

The **Buster Runtime Kernel** (Python event/scheduler/capability/security
layer) is explicitly distinct from the conventional Linux kernel.

## Layout

```
buster/
├── buster/
│   ├── version.py          # Central version definition
│   ├── config.py           # JSON-backed configuration system
│   ├── logging.py          # Logging subsystem
│   ├── kernel/             # Kernel / control plane
│   │   ├── core.py         # Lifecycle controller; wires every subsystem
│   │   ├── event_router.py # Single central event bus
│   │   ├── scheduler.py    # Priority + periodic job scheduling (job control)
│   │   ├── permissions.py  # Allow/deny permission gate
│   │   ├── world_model.py  # Versioned environment facts/snapshots
│   │   ├── agent_manager.py# Agent lifecycle registry
│   │   └── audit.py        # Append-only JSON-lines audit trail
│   ├── capabilities/       # Capability abstraction + registry + adapters
│   │   ├── base.py         # Capability / CapabilityContext / result types
│   │   ├── registry.py     # Dispatch with permission, elevation, events, audit
│   │   ├── adapters.py     # FunctionCapability + LegacyRouterAdapter
│   │   └── impl/           # Core capability implementations
│   │       ├── filesystem.py   # fs.* (with delete protection)
│   │       ├── shell.py        # shell.run / shell.check
│   │       ├── terminal.py     # terminal.open/write/close/run
│   │       ├── python_runner.py# python.eval / python.exec (jailed)
│   │       ├── git.py          # git status/log/branch/clone/add/commit/pull
│   │       ├── android.py      # android.info/battery/sensors
│   │       ├── process.py      # process.list/kill + system.info
│   │       └── network.py      # net.get/post/dns/ping
│   ├── ai_providers/       # Pluggable AI backends
│   │   ├── base.py         # AIProvider / AICompletion / AIMessage
│   │   ├── registry.py     # Named provider registry
│   │   ├── local.py        # On-device deterministic provider
│   │   └── remote.py       # OpenAI-compatible HTTP provider (stdlib only)
│   ├── agents/             # Agent interface and orchestration
│   │   ├── base.py         # Agent / AgentRun / AgentStatus
│   │   └── orchestration.py# goal -> plan -> capability execution loop
│   ├── memory/             # Memory subsystem
│   │   ├── core.py         # Persistent key/value store (TTL)
│   │   ├── experience.py   # Append-only experience log
│   │   ├── knowledge.py    # Learned knowledge with confidence
│   │   └── reflection.py   # Reflection engine + hooks
│   ├── perception/         # Perception subsystem
│   │   ├── base.py         # Sensor ABC + SensorHub
│   │   ├── device.py       # Device/Android platform facts
│   │   └── environment.py  # Environment/resources facts
│   ├── security/           # Security subsystem
│   │   ├── context.py      # ExecutionContext / SecurityContext
│   │   ├── protection.py   # Delete protection for sensitive paths
│   │   └── elevation.py    # Elevation approval for sensitive actions
│   ├── shell/              # Interactive shell
│   │   ├── parser.py       # Quote-aware command parser
│   │   ├── registry.py     # Command registry
│   │   ├── results.py      # StructuredResult rendering
│   │   └── session.py      # REPL + kernel dispatch + job control
│   ├── runtime.py          # Single-runtime lock, daemon server, RPC client
│   ├── gui/                # Consumer UI (client of the daemon; no Kernel)
│   │   ├── server.py       # Local HTTP/JSON GUI-RPC server
│   │   ├── __main__.py     # `python -m buster.gui.server`
│   │   └── web/            # Frontend: dark/purple design, orb, screens
│   ├── osbuild/            # Linux distribution/rootfs build system
│   │   ├── packages.py     # Debian Packages index parser
│   │   ├── deb.py          # .deb (ar/tar) reader/extractor
│   │   ├── resolver.py     # Dependency-closure resolver
│   │   ├── rootfs.py       # Rootfs layout + dpkg state + system layer
│   │   ├── identity.py     # Buster OS identity/service templates
│   │   ├── manifest.py     # Distribution manifests + checksums
│   │   └── migrate.py      # v0.2.0 -> system persistent-state migration
│   ├── system/             # Buster OS system integration (busterctl)
│   ├── bootstrap.py        # Offline install/init + runtime seed
│   ├── intelligence/       # Cognition layer (plugs into the single Kernel)
│   │   ├── nervous.py      # Basal nervous system: signals + node health
│   │   ├── rhythm.py       # Cognitive rhythm state machine
│   │   ├── attention.py    # Attention prioritization (noise-suppressed)
│   │   ├── memory.py       # Working/episodic/procedural + memory coordinator
│   │   ├── goals.py        # Persisted goal registry (not a scheduler)
│   │   ├── plans.py        # Persisted structured plans + replanning
│   │   ├── learning.py     # Context→…→lesson cycles, capability reliability
│   │   ├── reflection.py   # Bounded reflection (lessons/hypotheses/questions)
│   │   ├── curiosity.py    # Prioritized knowledge-gap questions
│   │   ├── agents.py       # Role configs over one PlannerAgent architecture
│   │   ├── proactive.py    # Non-executing suggestions
│   │   ├── maintenance.py  # Self-observation + bounded recovery
│   │   ├── providers.py    # Local-first provider health/selection
│   │   └── orchestration.py# Event-driven cognitive loop on the scheduler
│   ├── cli/                # `buster` command entry points
│   │   ├── main.py         # dispatch
│   │   └── commands.py     # lifecycle (bootstrap/start/status/shell/stop)
│   │                       # + management commands
│   ├── android_integration/# TerminalP / Termux-class detection + API
│   ├── diagnostics/        # Doctor / health checks
│   ├── workspace/          # Isolated workspaces with traversal guards
│   └── tests/              # Unit + integration + compatibility tests
├── config/                 # Default configuration
├── docs/                   # Documentation
├── installer.py            # Idempotent installation
└── launcher.py             # Kernel bootstrap
```

## Design rules

1. **One runtime.** Exactly one `Kernel` per process owns all subsystems.
2. **One event bus.** Cross-subsystem communication only via `EventRouter`.
3. **One scheduler.** `Scheduler` owns all timed/periodic work (job control).
4. **Dependency-free core.** stdlib only; swap-in heavy deps behind APIs.
5. **Deny by default.** Every action passes the permission + elevation gates.
6. **Event lifecycle.** Capability dispatch emits `capability.calling`,
   `capability.succeeded` / `capability.failed` and audits each outcome.

## Capability dispatch pipeline

```
shell/CLI/orchestrator
        |
        v
+----------------------+
| CapabilityRegistry   |
| call(action, extra,  |
|       context)       |
+----------------------+
   | 1. locate capability
   | 2. build ExecutionContext
   | 3. emit capability.calling
   | 4. permission gate + optional elevation
   | 5. capability.invoke(ctx)
   | 6. emit succeeded / failed + audit
   v
Capability implementation
```

## Security model

- Actions are **denied by default**; grants are explicit.
- Sensitive actions (`fs.delete`, `process.kill`, config/permission writes)
  additionally require **elevation approval**.
- The install, config, memory, log and state trees are **delete-protected**.
- Every dispatch outcome lands in the **audit trail** (`audit.jsonl`).

## Linux environment and distribution build

Buster OS is its own Linux environment built on a mature upstream foundation
(Debian bookworm, glibc, apt/dpkg). See
`docs/buster_os_foundation_decision.md` for the selection rationale.

System layout under Buster OS Linux:

- System/config: `/etc/buster`, `/usr/share/buster` (replaceable, packaged)
- Runtime state (transient): `/run/buster`
- Persistent intelligence state: `/var/lib/buster` (memories, goals, plans,
  permissions, identity)
- Logs: `/var/log/buster`
- Buster runtime components: `/opt/buster`
- User data: `/home/buster`, `/srv/buster`
- Migration from the v0.2.0 `~/.buster` layout: `buster/osbuild/migrate.py`

Distribution build (network-backed, reproducible):

```
python build_rootfs.py --arch amd64      # or arm64
python build_release.py                  # all enabled architectures + manifests
python build_release.py --candidates-check
```

Produces: `dist/buster-os-<version>-<arch>-<distro>.tar.gz`,
`manifest-<arch>.json` (resolved package versions, checksums, mirror,
snapshot), `verification-<arch>.json` (ELF/loader/dpkg/identity checks),
an authoritative `SHA256SUMS`, `release.json` and `candidates-report.json`.

Buster OS is ONE operating system and ONE source tree. Architectures are
release targets defined in `buster/osbuild/architectures.py` — enabled:
amd64, arm64 (constructed + structurally verified); candidate: i386, armhf,
armel, ppc64el, s390x, riscv64, mips64el (closure-evaluated). See
`docs/buster_arch_support_policy.md`. The rootfs is a full populated Linux
userspace; dpkg configuration completes at first boot (standard bootstrap
model). Buster is installed as a system component with systemd + sysvinit
service units and `busterctl`. Artifacts built here are structurally
verified; `runtime_executed` is set only when an artifact has actually been
exercised in a matching environment.