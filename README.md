# Buster OS

An AI-native operating environment for **Termux on Android**. Buster OS
provides a single runtime for AI agents on mobile: a unified event bus,
scheduler, capability system, memory subsystem, and Android integration.

## Status

Early foundation (v0.1.0):

- Kernel lifecycle (`start` / `stop` / `status`)
- Central event bus (`EventRouter`)
- Job scheduler with priorities, periodic tasks, cancellation
- Permission gate (deny by default)
- World model, agent manager, audit trail
- Capability registry, AI provider abstraction, agent interface
- Persistent memory, isolated workspaces
- Termux detection and doctor diagnostics
- `buster` CLI with `start` / `status` / `version` / `help`

## Requirements

- Termux on Android (aarch64 recommended)
- Python 3.10+
- Standard Linux utilities

## Installation

```sh
python installer.py
```

This creates `~/.buster/` with config, logs, cache, state, memory,
workspaces and backup directories, and writes an initial configuration.

## Usage

```sh
python launcher.py      # boot the kernel
python -m buster.cli start
python -m buster.cli status
python -m buster.cli version
```

## Tests

```sh
python -m unittest discover -s buster/tests -p "test_*.py"
```

## Documentation

See `docs/architecture.md` for the design rules and module layout.