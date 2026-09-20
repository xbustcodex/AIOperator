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
│   │   ├── core.py         # Lifecycle controller (single Kernel per process)
│   │   ├── event_router.py # Single central event bus
│   │   ├── scheduler.py    # Priority + periodic job scheduling
│   │   ├── permissions.py  # Allow/deny permission gate
│   │   ├── world_model.py  # Versioned environment facts/snapshots
│   │   ├── agent_manager.py# Agent lifecycle registry
│   │   └── audit.py        # Append-only JSON-lines audit trail
│   ├── capabilities/       # Capability abstraction + registry
│   ├── ai_providers/       # Pluggable AI backends
│   ├── agents/             # Agent interface and runs
│   ├── memory/             # Persistent key/value memory
│   ├── workspace/          # Isolated workspaces with traversal guards
│   ├── cli/                # `buster` command entry points
│   ├── android_integration/ # Termux / device detection
│   ├── diagnostics/        # Doctor / health checks
│   └── tests/              # Unit tests
├── config/                 # Default configuration
├── docs/                   # Documentation
├── installer.py            # Idempotent installation
└── launcher.py             # Kernel bootstrap
```

## Design rules

1. **One runtime.** Exactly one `Kernel` per process owns all subsystems.
2. **One event bus.** Cross-subsystem communication only via `EventRouter`.
3. **One scheduler.** `Scheduler` owns all timed/periodic work.
4. **Dependency-free core.** stdlib only; swap-in heavy deps behind APIs.
5. **Deny by default.** Every action passes the permission gate first.