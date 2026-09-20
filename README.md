# Buster OS

An AI-native operating environment for **Termux on Android**. Buster OS
provides a single runtime for AI agents on mobile: a unified event bus,
scheduler, capability system, memory subsystem, perception, security and an
interactive shell — all stdlib-only and built to run within typical Android
device constraints.

## Status

Foundational release (v0.1.0) covering the full kernel-to-shell stack:

- **Kernel**: lifecycle (`start`/`stop`/`status`), central event bus, job
  scheduler (priorities, periodics, cancellation), permission gate, world
  model, agent manager, audit trail.
- **Capability system**: registry with permission + elevation enforcement,
  event lifecycle and audit hooks, compatibility adapters
  (`FunctionCapability`, `LegacyRouterAdapter`).
- **Core capabilities**: filesystem, shell, terminal, Python (`eval`/`exec`),
  git, Android/Termux, process/system, networking.
- **AI**: provider registry, on-device local provider, OpenAI-compatible
  remote provider (stdlib only), agent orchestration loop.
- **Memory**: persistent store with TTL, experience log, learned knowledge,
  reflection engine.
- **Perception**: sensor abstraction with device and environment sensors.
- **Security**: deny-by-default, execution context, delete protection,
  elevation approval, audit trail.
- **Interactive shell**: quote-aware parser, command registry, kernel + 
  capability dispatch, job control, structured results.
- **CLI**: `start`, `status`, `doctor`, `version`, `shell`, plus management
  commands (`caps`, `run`, `grant`, `deny`, `config`, `jobs`, `audit`).

## Requirements

- Termux on Android (aarch64 recommended)
- Python 3.10+
- Standard Linux utilities (`git`, `ping`, shell)

## Installation

```sh
python installer.py
```

Creates `~/.buster/` with config, logs, cache, state, memory, workspaces and
backups, and writes an initial configuration.

## Usage

```sh
python launcher.py                       # boot the kernel and exit
python -m buster.cli start               # start kernel
python -m buster.cli status              # status snapshot
python -m buster.cli doctor              # environment health checks
python -m buster.cli shell               # interactive shell
python -m buster.cli run shell.run 'command=echo hi'  # direct capability call
```

### Interactive shell

```
buster> help                  # list commands
buster> status                # kernel status
buster> run shell.run command="echo hi"
buster> run python.eval code="2 ** 8"
buster> jobs                  # job control
buster> mem put note hello
buster> grant android.info    # allow an action
buster> plan inspect the device
```

By default every capability action is **denied** until explicitly granted
(`grant <action>`). Authentication and secrets live in `config/config.json`
(`ai_providers`), never in the repository.

## Tests

```sh
python -m unittest discover -s buster/tests -p "test_*.py"
```

Coverage: config, event router, kernel lifecycle, scheduler, permissions,
audit, capability registry + adapters, core capabilities, memory
(experience/knowledge/reflection), security (protection/elevation/context),
AI providers, perception, shell parser/session, and end-to-end integration.

## Documentation

- `docs/architecture.md` — design rules, module layout, dispatch pipeline.