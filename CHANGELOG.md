# Changelog

All notable changes to Buster OS are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-09-20

### Added
- Package skeleton with version, configuration, and logging subsystems.
- Kernel core with lifecycle control (`start` / `stop` / `status`).
- Central event bus (`EventRouter`) with sync/async dispatch.
- Priority scheduler with one-shot, periodic and cancellable jobs.
- Permission gate with grant/deny rules and deny-by-default behavior.
- Versioned world model and component state registry.
- Agent manager and concatenated agent interface.
- Append-only JSON-lines audit trail.
- Capability registry with permission-gated dispatch.
- AI provider abstraction layer.
- Persistent key/value memory with TTL.
- Isolated workspaces with path-traversal guards.
- Termux / Android detection and doctor health checks.
- `buster` CLI (`start`, `status`, `version`, `help`).
- Idempotent installer and kernel launcher.
- Unit tests for config, event router, scheduler, permissions, and audit.