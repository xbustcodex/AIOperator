# Buster OS

Buster OS is its own complete, general-purpose **Linux environment** — with
its own root filesystem, userspace, configuration, package environment,
identity and deployable distribution artifact — built on a mature upstream
Linux foundation (Debian stable). The existing Buster runtime/intelligence
architecture is installed as a native system component on top.

TerminalP is a separate Prime Tech application and **one** deployment
mechanism for Buster OS. Buster OS is not defined by TerminalP, Termux,
Android, Kali or any other host; it can be deployed through any suitable
Linux-hosting mechanism without changing what Buster OS is.

## Project

- **Buster runtime** (this repo's `buster/` package): single daemon Kernel,
  event router, scheduler, capabilities, permissions/elevation, audit, RPC,
  memory, perception, nervous system, rhythm/attention, learning,
  reflection, curiosity, goals, plans, agent roles, orchestration,
  interactive shell and CLI.
- **Linux distribution build** (`buster/osbuild/` + `build_rootfs.py`):
  reproducibly constructs a populated Buster OS rootfs from the Debian
  foundation, installs the Buster system layer, and produces a deployable
  artifact with manifests and checksums.
- **System integration** (`buster/system/`, `busterctl`): Buster as a Linux
  system component with `/etc/buster` configuration, `/var/lib/buster`
  persistent state, `/var/log/buster` logs and systemd/sysvinit services.

## Status

Foundational release (v0.1.0) covering the full kernel-to-shell stack:

- **Kernel**: lifecycle (`start`/`stop`/`status`), central event bus, job
  scheduler (priorities, periodics, cancellation), permission gate, world
  model, agent manager, audit trail.
- **Capability system**: registry with permission + elevation enforcement,
  event lifecycle and audit hooks, compatibility adapters
  (`FunctionCapability`, `LegacyRouterAdapter`).
- **Core capabilities**: filesystem, shell, terminal, Python (`eval`/`exec`),
  git, Android/TerminalP, process/system, networking.
- **AI**: provider registry, on-device local provider, OpenAI-compatible
  remote provider (stdlib only), agent orchestration loop.
- **Memory**: persistent store with TTL, experience log, learned knowledge,
  reflection engine.
- **Perception**: sensor abstraction with device and environment sensors.
- **Security**: deny-by-default, execution context, delete protection,
  elevation approval, audit trail.
- **Interactive shell**: quote-aware parser, command registry, kernel + 
  capability dispatch, job control, structured results, and intelligence
  commands (`intel`, `goal`, `reflect`, `consolidate`, `curiosity`,
  `provider`, `health`, `think`, `learn`, `exp`).
- **CLI**: `start`, `status`, `doctor`, `version`, `shell`, plus management
  commands (`caps`, `run`, `grant`, `deny`, `config`, `jobs`, `audit`,
  `intel`, `goal`, `health`).

## Requirements

- **TerminalP** on Android (Termux-class terminal; aarch64 recommended)
  — TerminalP is the host that runs the Buster OS phone node.
- Python 3.10+
- Standard Linux utilities (`git`, `ping`, shell, host `pkg`/API binaries)

## Installation

```sh
python installer.py
```

Creates `~/.buster/` with config, logs, cache, state, memory, workspaces and
backups, and writes an initial configuration.

## Distribution / Linux build

Build a reproducible, populated Buster OS rootfs (Debian foundation + Buster
system layer). Requires network access to the Debian archive.

```sh
python build_rootfs.py --arch amd64       # single architecture
python build_release.py                   # all enabled architectures (amd64 + arm64)
python build_release.py --candidates-check   # closure evaluation of candidate archs
```

Supported architectures: **amd64** and **arm64** (enabled, structurally
verified). Candidate architectures (i386, armhf, armel, ppc64el, s390x,
riscv64, mips64el) are evaluated at closure level; see
`docs/buster_arch_support_policy.md`.

Produces (per supported architecture and for the release):

- `dist/buster-os-<version>-<arch>-bookworm.tar.gz` — deployable rootfs
- `dist/manifest-<arch>.json` — resolved packages, versions, checksums
- `dist/verification-<arch>.json` — ELF/loader/dpkg/identity verification
- `dist/release.json`, `dist/candidates-report.json`, `dist/SHA256SUMS`

Verification is architecture-aware (ELF class/machine, dynamic loader, dpkg
database, Buster installation, filesystem identity) and now also inspects the
**archived** Unix metadata directly: executables (including the dynamic
loader) must be executable, configuration/data files must not be, directories
must be searchable, and merged-/usr aliases must be symlinks. Package file
modes are preserved from `.deb` payloads through an authoritative metadata
overlay (never re-derived from staging-FS stat). Artifacts built here are
constructed and structurally verified; `runtime_executed` is set only when an
artifact has actually been booted in a matching environment.

```sh
busterctl bootstrap
busterctl start
busterctl status
```

## Bootstrap

Bootstrap is the **installation/initialization** phase; it never boots a
runtime and never constructs a Kernel. It materializes the install layout,
default configuration and the first-run marker — all idempotent.

```sh
python bootstrap.py                  # offline bootstrap
python bootstrap.py --check          # bootstrap + doctor health checks
python -m buster.cli bootstrap       # same via the CLI
```

## Runtime lifecycle

`start` brings the single runtime online and `stop` takes it down. A PID +
heartbeat lock in `install/state/` guarantees **exactly one Kernel instance
per install**; a second `start` is refused. `status` and `shell` are
read-only clients (they never create a Kernel of their own) that talk to the
daemon over a file-based JSON request/response channel.

```sh
python -m buster.cli start           # daemon comes online (single kernel)
python -m buster.cli status          # state, PID, heartbeat, capabilities
python -m buster.cli shell           # interactive shell attached to the runtime
python -m buster.cli stop            # clean shutdown, lock released
```

Runtime verification runs standalone (lock semantics, RPC op surface,
cross-process daemon boot):

```sh
python buster/tests/check_runtime.py
```

## Build

The build script compiles every module, runs the full test suite,
smoke-tests the CLI, and packages a clean distribution zip.

```sh
python build.py                      # compile + tests + package
python build.py --skip-tests         # skip the test run
```

Produces `dist/buster-os-<version>.zip`.

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