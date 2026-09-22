# Changelog

All notable changes to Buster OS are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [Semantic Versioning](https://semver.org/).

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