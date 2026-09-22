# AGENTS.md — Buster OS Product, Architecture, Integration, GUI, and Update Contract

## Purpose

This file defines the product direction, architectural invariants, integration rules, user-experience goals, and release/update process for Buster OS.

Any coding agent working in this repository must read and preserve these decisions before making architectural changes.

Buster OS is not a generic Linux distribution and it is not merely an AI application running in a terminal. It is the full Buster phone node: a Linux-based operating environment built around Buster, with Buster as the persistent intelligence/runtime layer and TerminalP as the native Prime Tech phone host.

The objective is to use Linux as the mature backbone and build the Buster-specific operating environment, intelligence, services, GUI, integrations, and update system around it.

---

## 1. Product Definition

Buster OS is the actual Buster product/runtime for the phone.

It consists of two major layers:

### Buster Backbone

The Linux-based Buster OS/runtime is Buster's persistent backbone.

It owns or integrates:

- Kernel/runtime lifecycle
- Single daemon runtime
- Event system
- Scheduler/jobs
- RPC/RemoteKernel
- Capability system
- Permissions/elevation/security
- Audit
- Nervous system
- Perception/sensors
- World model
- AI providers
- Planning
- Agents
- Memory
- Experience
- Learning
- Knowledge
- Reflection
- Goals/tasks
- Device integration
- TerminalP integration
- Package/update integration
- Diagnostics/recovery

Linux provides the mature underlying facilities Buster should not reinvent: filesystem, processes, networking, packages, shell, libraries, IPC, standard utilities, Python, Git, and related system tooling.

### Buster Front Node

The front node is the normal user's interface to Buster.

It is not another Buster runtime and does not own Buster's intelligence.

It connects to the existing Buster runtime through the controlled Kernel/RPC interface.

The front node can evolve independently while Buster's memory, intelligence, agents, services, and runtime continue operating underneath.

---

## 2. Prime Tech Ecosystem

Buster must be designed as part of the Prime Tech ecosystem.

### TerminalP

TerminalP is a separate Prime Tech application and **one possible deployment
mechanism** for Buster OS. Buster OS is NOT defined by TerminalP, Termux,
Android, Kali or any other particular host or deployment mechanism.

Buster OS is its own complete, general-purpose Linux environment with its own
root filesystem, userspace, configuration, package environment, services and
identity. It can be deployed through any suitable Linux-hosting mechanism
(TerminalP, Termux-class Android terminals, a VM, a container, an ARM
machine, a conventional Linux host, or a cloud image) without changing what
Buster OS is.

TerminalP intentionally remains compatible with the underlying Termux-class
Linux/package mechanisms where useful. Preserve compatible low-level
mechanisms rather than unnecessarily rewriting working Linux infrastructure;
treat TerminalP-as-deployment as one integration surface, never as the
definition of the operating system.

The distinction is:

- Product/platform identity: TerminalP
- Compatibility mechanisms: Termux-class Android/Linux mechanisms where TerminalP legitimately uses them
- Buster runtime identity: Buster OS

Do not blindly rename low-level commands or paths merely because they contain "termux". Determine whether each reference represents product identity or a required compatibility mechanism.

### TerminalP File Manager

The existing file-manager application is to become the normal-user graphical file-management application for the TerminalP/Prime Tech ecosystem.

It should remain useful as a standalone GUI application while integrating naturally with TerminalP and Buster.

Long-term integration should allow workflows such as:

- TerminalP opening a directory in TerminalP File Manager
- TerminalP File Manager opening a selected location in TerminalP
- Buster locating files and handing the location to TerminalP File Manager
- Buster performing permitted filesystem operations while the GUI reflects the result

Do not duplicate filesystem engines unnecessarily.

### Other Prime Tech Software

Future Prime Tech applications should remain individually useful but become more capable when used together.

Buster should expose stable integration boundaries so future applications can communicate with the Buster node rather than recreating Buster's intelligence.

---

## 3. Architectural Invariants

These are permanent unless deliberately superseded by an explicit architectural decision.

There must be:

- ONE Kernel
- ONE live runtime daemon
- ONE scheduler/job authority
- ONE event system
- ONE agent architecture
- ONE source of runtime truth

Do not introduce:

- A second hidden Kernel
- GUI-owned Buster runtimes
- Shell-owned execution engines
- Parallel schedulers
- Independent autonomy loops
- Duplicate agent frameworks
- Separate memory authorities
- Hidden capability execution paths

The shell, GUI, CLI, and future applications are clients of the running Buster node.

Closing a GUI must not kill Buster's persistent runtime, memory, jobs, or intelligence.

All real system-changing actions must continue through Buster's authority chain:

ExecutionContext
→ permission/elevation
→ capability
→ execution
→ event
→ audit

Knowledge is not permission.
Memory is not permission.
A plan is not permission.
An agent is not permission.
A learned procedure is not permission.

---

## 4. Bootstrap and Runtime Separation

Preserve the bootstrap invariant.

Bootstrap is installation, initialization, reconciliation, migration, validation, and update infrastructure.

Bootstrap must not become the Buster runtime and must not construct a second Kernel.

Runtime execution remains owned by the single Buster daemon.

Conceptually:

Buster package/release
→ bootstrap/update engine
→ install/update modules
→ migrate persistent state if required
→ validate installation
→ Buster start
→ one Kernel/runtime

Bootstrap should remain idempotent.

Running bootstrap repeatedly must not:

- Duplicate registrations
- Duplicate scheduled work
- Create another runtime
- Destroy user state
- Reset Buster's identity
- Corrupt configuration
- Re-run unsafe migrations

---

## 5. Linux and Package Strategy

Buster OS is its own complete, general-purpose Linux environment. It owns its
Linux root filesystem, userspace, system configuration, package environment,
Buster system components, persistent-state architecture, identity, build
process and deployable distribution artifact.

Do not build a new Linux kernel/distribution from scratch merely to call it
Buster. Use a mature, proven general-purpose Linux foundation (Debian stable
is the selected upstream foundation) and build the Buster environment around
it. Buster does not reinvent standard Linux facilities.

Linux is the backbone that allows Buster to use mature packages, services,
processes, networking, storage, graphics, development tooling, and libraries.

Distinctions that must remain explicit:

- **Buster Runtime Kernel** (the Python/runtime execution and control kernel)
  is distinct from the **conventional Linux kernel**. The Buster Runtime
  Kernel is Buster's event/scheduler/capability/security/RPC control layer.
- Upstream Linux components retain their own provenance, copyright, licensing
  and notices. Buster/Prime Tech integration and packaging, and original
  Buster software, are separately identified.

Buster-specific functionality is delivered as versioned capabilities and
system components on top of the foundation, and uses the foundation's mature
package management (apt/dpkg) rather than an incompatible package manager.

The long-term user-facing update model should feel like a normal Linux system:

    apt update
    apt upgrade

Buster's bootstrap/update machinery handles Buster-specific installation,
reconciliation, migrations, validation, and restart/reload requirements.

Possible future package separation may include concepts such as:

- buster-core
- buster-intelligence
- buster-memory
- buster-agents
- buster-perception
- buster-gui
- buster-terminalp-deploy

Do not force package splitting prematurely. Use it when it improves
maintainability and release management.

---

## 6. Update Contract

Every new Buster feature must be designed for rollout through the established update process.

Do not create one-off manual installation procedures for new Buster subsystems.

Expected release flow:

Develop
→ integrate with existing Buster runtime
→ test
→ version
→ package
→ update bootstrap/install manifests
→ add migrations when needed
→ publish through Prime Tech/TerminalP package infrastructure
→ apt update / apt upgrade
→ bootstrap/update reconciliation
→ validate
→ restart/reload as required
→ same Buster, newer version

A software update must not mean resetting Buster.

Persistent data must be separated from replaceable application/runtime files.

Appropriate persistent state includes:

- Memory
- Experience
- Learned knowledge
- User preferences
- Permissions
- Projects
- Goals/tasks where appropriate
- Configuration
- Important world-state history
- User-created data

Upgrade tests must include both:

1. Fresh installation → works
2. Previous supported release → upgrade/migrate → restart → existing state preserved → new release works

Versioned migrations must be used when schemas or persistent formats change.

---

## 7. Buster Intelligence Direction

Buster is intended to become one coherent intelligent system, not a collection of disconnected AI features.

The desired cognitive flow is:

SENSE
→ UNDERSTAND
→ REMEMBER
→ ATTEND
→ THINK
→ PLAN
→ ACT
→ OBSERVE
→ LEARN
→ REFLECT
→ ADAPT

All of this must remain inside the existing single-runtime architecture.

### Basal/Nervous System

Buster should have a lightweight always-running nervous-system layer that does not require continuous LLM inference.

It should maintain useful awareness of:

- Heartbeat/runtime health
- Activity and idle state
- Battery/charging
- CPU/memory/storage pressure
- Network/connectivity
- Device/environment changes
- Capability availability
- Service health
- Job/agent activity
- Recent failures
- Permission/elevation state
- Memory health
- AI-provider availability
- TerminalP host state

Raw sensor noise should be converted into useful internal signals.

### Cognitive Rhythm and Attention

Buster should distinguish states such as:

- Active interaction
- Background operation
- Idle
- Reflection opportunity
- Maintenance opportunity
- Resource-constrained state
- Degraded connectivity
- Recovery
- Low-activity/sleep-like state where appropriate

Attention should prioritize meaningful changes according to relevance, urgency, novelty, active goals, and available resources.

Routine sensor noise must not continuously invoke expensive cognition.

### World Model

The world model should represent Buster, TerminalP, the Android device, capabilities, environment, tasks, goals, projects, recent events, important entities, resources, failures, and unresolved situations.

Distinguish observations from inferences and uncertainty.

Track provenance/timestamps where appropriate.

Do not turn the world model into an uncontrolled event dump.

### Memory

Memory should evolve into coherent working, short-term/context, episodic, experience, semantic/knowledge, procedural, reflection, learned-lesson, and important historical memory where appropriate.

Memory should support:

- Storage
- Retrieval
- Search
- Relevance
- Provenance
- Timestamps
- Confidence where useful
- Deduplication
- Consolidation
- TTL/expiry where useful
- Promotion
- Pruning/forgetting
- Goal/task/action relationships
- Diagnostics/statistics

Retrieve relevant memory for reasoning. Do not inject the entire memory store into prompts.

### Learning and Experience

Capture meaningful cycles:

context
→ intention
→ plan
→ action
→ result
→ evaluation
→ lesson

Learn from successes, failures, repeated failures, user corrections, capability outcomes, planning outcomes, environmental changes, recurring workflows, tool reliability, and previously solved problems.

Learning must never silently grant authority.

### Reflection

Reflection should be bounded and event/rhythm driven.

Useful triggers include:

- Meaningful task completion
- Significant failure
- Repeated similar failure
- Suitable idle periods
- Memory consolidation
- Contradictory knowledge

Reflection may produce lessons, hypotheses, unresolved questions, memory links, planning improvements, knowledge updates, and suggested capability improvements.

Reflection must not bypass security.

### Curiosity

Curiosity should detect useful knowledge gaps related to goals, repeated problems, capabilities, projects, device/environment, and user requests.

Curiosity should create explicit questions/hypotheses, not uncontrolled autonomous activity.

### Goals and Planning

Goals should support provenance, priority, dependencies, progress, blockers, completion/failure, and cancellation.

Goals are not another scheduler.

Planning should reason over:

- User request
- World state
- Relevant memory
- Capabilities
- Permissions
- Resource constraints
- Experience
- Active goals

Plans should be structured and capability-based.

Agents must not smuggle raw execution around the capability/security architecture.

### Agents

Use one reusable agent architecture.

Useful roles may include:

- Planner
- Researcher
- Builder
- Tester
- Reviewer
- Fixer
- Observer
- Memory/knowledge worker
- Maintenance worker

Agents share the same Kernel, scheduler, event system, capabilities, execution context, permissions, memory, and audit infrastructure.

### Proactive Intelligence

Buster may proactively recognize meaningful conditions such as recurring failures, resource problems, broken capabilities, stalled jobs, important state changes, unfinished goals, useful maintenance opportunities, and learned patterns.

Proactivity should become structured signals, suggestions, goals, or permitted actions.

Do not make Buster noisy.

Do not bypass user authority.

---

## 8. GUI Product Direction

The GUI is now a major product priority.

It is for ordinary everyday users, including people who do not understand Linux, Windows administration, terminals, kernels, RPC, agents, or AI-provider configuration.

The underlying system can be extremely sophisticated.

The normal interface must remain simple.

### Core UX Principle

Buster can be enormously complicated underneath and extremely simple on top.

Do not expose technical implementation terminology to normal users unless they deliberately enter an Advanced/Developer area.

Normal users should not have to understand:

- Kernel
- RPC
- ExecutionContext
- Capability dispatch
- Provider routing
- Scheduler internals
- Agent internals
- Linux administration

Translate technical states into normal language.

Examples:

Instead of:
"Capability permission denied: fs.delete"

Use:
"Buster needs permission to delete this file."

Instead of:
"Remote provider unavailable; local provider selected"

Use:
"I'm offline, but I can still help with most things on this device."

Routine maintenance such as memory consolidation should normally require no user-facing notification.

---

## 9. Purple Orb — Preserve It

The purple orb is Buster's primary visual presence.

Do not redesign it away.

It is an intentional product element because it gives users a clear visual focus while Buster is listening, thinking, working, or speaking.

The orb should become a stateful visual indicator.

Suggested states:

- Idle: subtle slow movement
- Listening: responsive voice/input animation
- Thinking: deeper internal motion/pulsing
- Working: more active but calm motion
- Speaking: movement loosely synchronized with speech
- Needs attention: restrained pulse plus understandable message
- Offline/local mode: preserve Buster identity; use a subtle status indicator

Do not use distracting or alarming animation.

The orb should be persistent across the product:

- Large in voice/live mode
- Prominent on Home
- Smaller in headers/activity surfaces
- Suitable as a recognizable Buster identity throughout the Prime Tech ecosystem

The existing purple-orb visual reference is the baseline inspiration for the first consumer GUI. Use its simplicity, dark/purple visual language, mobile-first proportions, and focused assistant experience as inspiration, while producing a distinct Buster/Prime Tech product rather than copying another interface pixel-for-pixel.

---

## 10. Buster GUI v1

The first consumer GUI release should establish a permanent frontend architecture.

It should be a real frontend connected to the actual Buster daemon through RPC/RemoteKernel, not a mock application.

### Onboarding

Simple first-run experience:

Welcome
→ basic setup
→ permissions/privacy where required
→ Buster ready

Do not make users configure Linux.

### Home

Home should prioritize:

- Buster purple orb
- Simple greeting/status
- Ask Buster
- Voice entry
- Context-sensitive quick actions
- Recent/useful activity
- Files
- Tasks
- Projects
- Device
- Other useful consumer surfaces

Avoid a technical dashboard as the default landing page.

### Conversation

Support:

- Text chat
- Voice
- Conversation history
- Listening state
- Thinking state
- Working state
- Speaking state
- Cancel/stop where appropriate

### Everyday Tools

Expose normal concepts such as:

- My Files
- Tasks
- Projects
- Device
- Notifications
- Recent activity

Integrate with TerminalP File Manager instead of rebuilding a complete graphical file browser inside Buster.

### Buster Memory

Expose useful memory in understandable consumer language.

Users should be able to understand what Buster remembers or has learned without navigating internal databases.

### Settings

Normal settings should cover things ordinary users care about:

- General preferences
- Voice
- Notifications
- Privacy
- Permissions
- Appearance where appropriate
- Buster behavior/preferences

Technical configuration belongs in Advanced.

### Advanced / Developer

Keep the full technical power available, but separate it from everyday use.

Advanced surfaces may expose:

- Kernel/runtime
- Agents
- Jobs
- Scheduler
- Capabilities
- Audit
- Providers
- Nervous system
- World model
- Memory stores
- Sensors
- TerminalP integration
- Logs
- Diagnostics
- Developer tooling

Same Buster. Same runtime. Different level of abstraction.

---

## 11. GUI Architecture

The GUI is a client of Buster.

Preferred conceptual boundary:

Buster GUI
↕
controlled GUI/RPC interface
↕
RemoteKernel/RPC
↕
single Buster daemon
↕
Kernel and services

The GUI must not instantiate its own Kernel.

The GUI must not duplicate Buster's memory, scheduler, agents, or capability execution.

The architecture should allow additional interfaces later without rewriting Buster:

- Phone GUI
- Desktop client
- Web interface
- Voice-only interface
- Prime Tech companion applications

Multiple interfaces may communicate with the same Buster node through controlled interfaces.

---

## 12. Consumer Experience

The user should experience Buster as a normal polished application.

Conceptually:

Install
→ launch Buster
→ Buster is there

The user should not need to know that Buster has:

- Bootstrapped a Linux environment
- Started a daemon
- Connected over RPC
- Initialized memory
- Started sensors
- Loaded capabilities
- Selected AI providers

Those are implementation details.

Buster should translate system complexity into clear human language and actions.

The deeper Buster becomes internally, the simpler the normal experience should feel.

---

## 13. Prime Tech Cross-App Experience

The ecosystem should feel integrated rather than like unrelated applications.

Examples:

User:
"Buster, find the photos I downloaded yesterday."

Buster finds them and presents useful results.

User selects:
"Open folder"

TerminalP File Manager opens at the correct location.

Or:

User:
"Put these files into a folder called Holiday."

Buster uses the permitted filesystem capability and TerminalP File Manager reflects the result.

The user does not need to know which internal Prime Tech component performed each operation.

Keep integration boundaries clean so each application remains maintainable.

---

## 14. First GUI Package and Future Expansion

The first GUI package does not need every future screen.

It must establish:

- Correct frontend architecture
- High-quality onboarding
- Home
- Purple orb and visual states
- Chat
- Voice
- History
- Everyday tools
- TerminalP File Manager integration
- Tasks/projects/device surfaces
- Understandable memory/activity
- Notifications
- Settings/privacy/permissions
- Advanced technical area
- Real RPC connection to Buster OS
- Package/bootstrap/update integration

Once this baseline is deployed, future features should roll out through normal Buster package updates rather than replacing the frontend foundation.

---

## 15. Release Discipline for GUI and Intelligence

The GUI follows the same update rules as every other Buster component.

Do not create a separate unmanaged GUI installer/update mechanism.

GUI releases should be versioned, packaged, installed/upgraded through the Prime Tech/TerminalP package pipeline, and reconciled through the Buster bootstrap/update system.

Future updates must preserve Buster's state and identity.

The intended user update experience is eventually:

    apt update
    apt upgrade

After which Buster-specific migration/reconciliation/validation occurs automatically as required.

---

## 16. Development Rules for Coding Agents

Before changing Buster:

1. Inspect the existing implementation.
2. Trace imports/runtime ownership.
3. Identify whether code belongs to the current Buster runtime, compatibility plumbing, or legacy/unrelated skeletons.
4. Preserve working architecture.
5. Extend the existing single runtime rather than creating parallel systems.
6. Preserve TerminalP as the first-class phone host.
7. Preserve compatible low-level mechanisms when they remain technically required.
8. Keep consumer UI language nontechnical by default.
9. Keep advanced engineering controls available separately.
10. Integrate every new release into the package/bootstrap/update process.
11. Add upgrade/migration tests when persistent state changes.
12. Run the complete existing test/build/runtime verification after significant changes.
13. Fix regressions before considering a build complete.
14. Keep documentation/versioning/package metadata current.
15. Leave the repository clean and runnable.

Do not stop at a roadmap when the task explicitly requests a complete build.

Do not divide a requested complete build into artificial phases unless technically necessary or explicitly requested.

---

## 17. Current Baseline

The current architectural baseline already includes the following concepts and must not be casually regressed:

- Buster OS v0.1.x foundation
- Complete Linux environment (rootfs + userspace + package environment) built atop a mature upstream Linux foundation; own identity, configuration, services and persistent-state architecture
- Single daemon Kernel/runtime
- Atomic runtime locking/heartbeat
- Bootstrap that performs install/init rather than constructing a Kernel
- File-based RPC and RemoteKernel
- Capability registry/dispatch
- ExecutionContext
- Deny-by-default permissions/elevation
- Audit
- Core filesystem/shell/terminal/Python/Git/Android/process/system/network capabilities
- AI provider abstraction
- Agent orchestration / planner / roles
- Persistent memory / intelligence (memory, experience, knowledge, reflection, goals, plans)
- Sensors/perception / nervous system / rhythm / attention / world model
- Interactive shell
- CLI lifecycle
- TerminalP first-class deployment compatibility (Termux-class mechanisms retained only where technically appropriate)
- Rootfs distribution builder, manifests and checksums
- Package/build verification
- Cross-process lifecycle verification

Treat the repository itself and its tests as the authoritative source for exact current implementation details.

---

## 18. Long-Term Product Principle

Buster OS should become the full dedicated Buster application and phone node.

Linux is Buster's backbone.

TerminalP is the native Prime Tech phone/Linux host and one deployment
mechanism for Buster OS.

The Buster runtime is the persistent intelligence/control layer.

The Buster GUI is the normal user's window into that runtime.

The Buster Runtime Kernel is the Buster event/scheduler/capability/security/
RPC control layer and is explicitly distinct from the conventional Linux
kernel. Buster uses mature upstream Linux components rather than recreating
the Linux ecosystem, and the architecture supports Buster evolving into a
publicly distributable Linux environment in its own right.

TerminalP File Manager and other Prime Tech applications are integrated ecosystem components.

The product should be approachable enough that a person with no Linux or Windows administration knowledge can open Buster like a normal application and use it immediately.

At the same time, the architecture must remain powerful enough to expand into additional applications, interfaces, capabilities, devices, and services without rebuilding Buster's core.

Build complexity underneath.
Deliver simplicity on top.
Preserve Buster across updates.
