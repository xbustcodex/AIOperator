# Buster OS Architecture

Buster OS is an AI-native operating environment for **Termux on Android**,
built with strict architectural discipline: one runtime, one event bus, one
scheduler, one source of truth.

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
│   ├── cli/                # `buster` command entry points
│   ├── android_integration/ # Termux / device detection
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