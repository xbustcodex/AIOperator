"""Interactive shell session for Buster OS.

A REPL that parses input, dispatches through the CommandRegistry, invokes
capabilities directly from the ``run <action>`` command, and offers job
control backed by the kernel scheduler.
"""

import json
import logging
import time
from typing import Optional

from buster.shell.parser import Command, parse
from buster.shell.registry import CommandRegistry
from buster.shell.results import StructuredResult
from buster.version import get_version


class InteractiveShell:
    """REPL bound to a running Kernel."""

    PROMPT = "buster> "

    def __init__(self, kernel=None):
        self.kernel = kernel
        self.logger = logging.getLogger("buster.shell")
        self.registry = CommandRegistry()
        self._register_builtins()
        self.running = False

    # -- registration --------------------------------------------------

    def _register_builtins(self) -> None:
        r = self.registry
        r.register("help", self._cmd_help, "show this help")
        r.register("version", self._cmd_version, "print Buster version")
        r.register("status", self._cmd_status, "kernel/runtime status")
        r.register("echo", self._cmd_echo, "echo arguments back")
        r.register("exit", self._cmd_exit, "leave the shell")
        r.register("quit", self._cmd_exit, "leave the shell")
        r.register("run", self._cmd_run, "invoke a capability action: run <action> [k=v ...]")
        r.register("caps", self._cmd_caps, "list registered capabilities/actions")
        r.register("grant", self._cmd_grant, "grant permission: grant <action>")
        r.register("deny", self._cmd_deny, "deny permission: deny <action>")
        r.register("eval", self._cmd_eval, "evaluate python through the python capability")
        r.register("jobs", self._cmd_jobs, "list scheduler jobs; 'jobs cancel <id>'")
        r.register("mem", self._cmd_mem, "show persistent memory; 'mem put <k> <v>'")
        r.register("audit", self._cmd_audit, "show recent audit tail")
        r.register("plan", self._cmd_plan, "run an orchestrator agent over a goal")
        r.register("think", self._cmd_think, "run the deliberate planner agent: think <goal>")
        r.register("learn", self._cmd_learn, "show learned knowledge: learn [prefix]")
        r.register("exp", self._cmd_exp, "show experience statistics")
        r.register("sensors", self._cmd_sensors, "collect perception sensor snapshot")
        r.alias("?", "help")

    # -- REPL ----------------------------------------------------------

    def run_one(self, line: str) -> StructuredResult:
        """Execute one input line; the core of the shell."""
        command = parse(line)
        if command is None:
            return StructuredResult.success("", "")
        if command.name in ("exit", "quit"):
            return self._cmd_exit(self, command)
        return self.registry.dispatch(self, command)

    def repl(self, input_fn=None, output_fn=print) -> int:
        """Blocking read/eval/loop. Returns the shell exit code."""
        self.running = True
        if input_fn is None:
            lines = iter(_input_gen())
        elif callable(input_fn):
            lines = iter(input_fn())
        else:
            lines = iter(input_fn)
        banner = f"Buster OS {get_version()} - type 'help' for commands."
        output_fn(banner)
        try:
            while self.running:
                try:
                    line = next(lines)
                except (EOFError, StopIteration):
                    break
                if line is None:
                    break
                line = line.strip()
                if not line:
                    continue
                result = self.run_one(line)
                rendered = result.render()
                if rendered:
                    output_fn(rendered)
                if result.command == "exit" and result.ok:
                    break
        except KeyboardInterrupt:
            output_fn("")
        finally:
            self.running = False
        return 0

    # -- built-in command handlers -------------------------------------

    def _cmd_help(self, shell, cmd: Command) -> StructuredResult:
        lines = []
        for name in self.registry.names():
            spec = self.registry.resolve(name)
            lines.append(f"{name:<10} {spec.help if spec else ''}")
        return StructuredResult.success("help", "\n".join(lines), title="Commands:")

    def _cmd_version(self, shell, cmd: Command) -> StructuredResult:
        return StructuredResult.success("version", get_version())

    def _cmd_status(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("status", "no kernel bound")
        body = ["=" * 30, "Kernel", "=" * 30]
        for key, value in self.kernel.status().items():
            body.append(f"{key:<24} {value}")
        return StructuredResult.success("status", "\n".join(body))

    def _cmd_echo(self, shell, cmd: Command) -> StructuredResult:
        return StructuredResult.success("echo", " ".join(cmd.args))

    def _cmd_exit(self, shell, cmd: Command) -> StructuredResult:
        self.running = False
        return StructuredResult.success("exit", "bye.")

    def _cmd_caps(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("caps", "no kernel bound")
        lines = ["Capabilities:"] + [f"  {name}" for name in self.kernel.cap.list_capabilities()]
        lines.append("Actions:")
        lines += [f"  {action}" for action in self.kernel.cap.list_actions()]
        return StructuredResult.success("caps", "\n".join(lines))

    def _cmd_run(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("run", "no kernel bound")
        if not cmd.args:
            return StructuredResult.failure("run", "usage: run <action> [k=v ...]")
        action = cmd.args[0]
        params = {}
        for arg in cmd.args[1:]:
            if "=" in arg:
                key, _, value = arg.partition("=")
                params[key] = parse_scalar(value)
        if cmd.option("async"):
            job = self.kernel.cap.run_async(action, extra=params,
                                            context={"actor": "shell", "source": "shell"})
            return StructuredResult.success("run", f"scheduled job {job.id[:8]} "
                                                   f"({job.name})")
        result = self.kernel.cap.call(action, extra=params,
                                      context={"actor": "shell", "source": "shell"})
        if not result.success:
            return StructuredResult.failure(action, result.error or "capability failed")
        if len(cmd.args) == 1:
            body = fast_stringify(result.data)
        else:
            return StructuredResult.success(action, json.dumps(result.data, default=str, indent=2)
                                            if result.data is not None else "OK")
        return StructuredResult.success(action, body)

    def _cmd_grant(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("grant", "no kernel bound")
        if not cmd.args:
            return StructuredResult.failure("grant", "usage: grant <action>")
        action = cmd.args[0]
        self.kernel.permissions.grant(action, note="granted via shell")
        return StructuredResult.success("grant", f"granted: {action}")

    def _cmd_deny(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("deny", "no kernel bound")
        if not cmd.args:
            return StructuredResult.failure("deny", "usage: deny <action>")
        action = cmd.args[0]
        self.kernel.permissions.deny(action, note="denied via shell")
        return StructuredResult.success("deny", f"denied: {action}")

    def _cmd_eval(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("eval", "no kernel bound")
        code = " ".join(cmd.args)
        result = self.kernel.cap.call("python.eval", extra={"code": code},
                                      context={"actor": "shell"})
        if not result.success:
            return StructuredResult.failure("eval", result.error or "eval failed")
        return StructuredResult.success("eval", json.dumps(result.data, default=str))

    def _cmd_jobs(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("jobs", "no kernel bound")
        scheduler = self.kernel.scheduler
        if cmd.args and cmd.args[0] == "cancel":
            if len(cmd.args) < 2:
                return StructuredResult.failure("jobs", "usage: jobs cancel <id>")
            cancelled = scheduler.cancel(cmd.args[1])
            return (StructuredResult.success("jobs", f"cancelled {cmd.args[1]}") if cancelled
                    else StructuredResult.failure("jobs", f"no pending job {cmd.args[1]}"))
        jobs = scheduler.list_jobs()
        if not jobs:
            return StructuredResult.success("jobs", "no jobs")
        body = [f"{job.id[:8]:<10} {job.status.value:<10} {job.name:<28} "
                f"{'periodic' if job.periodic else 'one-shot'}"]
        return StructuredResult.success("jobs", "\n".join(body), title="Scheduler jobs:")

    def _cmd_mem(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("mem", "no kernel bound")
        if cmd.args and cmd.args[0] == "put":
            key = cmd.args[1]
            value = " ".join(cmd.args[2:])
            self.kernel.memory.store.put(key, value)
            return StructuredResult.success("mem", f"saved: {key}")
        if cmd.args:
            return StructuredResult.success("mem",
                                           str(self.kernel.memory.store.get(cmd.args[0], None)))
        keys = self.kernel.memory.store.keys()
        return StructuredResult.success("mem", "\n".join(keys) or "(empty)")

    def _cmd_audit(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("audit", "no kernel bound")
        entries = self.kernel.audit.tail(limit=cmd.option("limit", 10))
        body = []
        for entry in entries:
            body.append(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['ts']))} "
                        f"{entry['action']:<28} actor={entry.get('actor', '')}")
        return StructuredResult.success("audit", "\n".join(body) or "(empty)", title="Audit tail:")

    def _cmd_plan(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("plan", "no kernel bound")
        goal = " ".join(cmd.args)
        if not goal:
            return StructuredResult.failure("plan", "usage: plan <goal text>")
        runner = getattr(self.kernel, "run_plan", None)
        if runner is not None:
            run = runner(goal)
            body = [f"status: {run.get('status')}"]
            if run.get("error"):
                body.append(f"error: {run['error']}")
            if run.get("result") is not None:
                body.append(json.dumps(run["result"], default=str, indent=2))
            return StructuredResult.success("plan", "\n".join(body))
        from buster.agents.orchestration import AgentOrchestrator
        agent = AgentOrchestrator(kernel=self.kernel)
        run = agent.run(goal)
        body = [f"status: {run.status.value}"]
        if run.error:
            body.append(f"error: {run.error}")
        if isinstance(run.result, dict):
            body.append(json.dumps(run.result, default=str, indent=2))
        return StructuredResult.success("plan", "\n".join(body))

    def _cmd_think(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("think", "no kernel bound")
        goal = " ".join(cmd.args)
        if not goal:
            return StructuredResult.failure("think", "usage: think <goal text>")
        runner = getattr(self.kernel, "run_planner", None)
        if runner is not None:
            run = runner(goal)
        else:
            from buster.agents.planner import PlannerAgent
            run = PlannerAgent(kernel=self.kernel).run(goal).__dict__
        body = [f"status: {run.get('status')}"]
        if run.get("error"):
            body.append(f"error: {run['error']}")
        if run.get("result") is not None:
            body.append(json.dumps(run["result"], default=str, indent=2))
        return StructuredResult.success("think", "\n".join(body))

    def _cmd_learn(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None or getattr(self.kernel, "memory", None) is None:
            return StructuredResult.failure("learn", "no memory subsystem bound")
        prefix = cmd.args[0] if cmd.args else ""
        entries = self.kernel.memory.knowledge.search(prefix, limit=cmd.option("limit", 20))
        if not entries:
            return StructuredResult.success("learn", "(no knowledge)")
        body = [f"{e['key']}: {e['value']}" for e in entries]
        return StructuredResult.success("learn", "\n".join(body))

    def _cmd_exp(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None or getattr(self.kernel, "memory", None) is None:
            return StructuredResult.failure("exp", "no memory subsystem bound")
        stats = self.kernel.memory.experience.stats()
        body = [
            f"total={stats['total']} done={stats['done']} failed={stats['failed']} "
            f"success_rate={stats['success_rate']}",
        ]
        if stats["top_goals"]:
            body.append("top goals:")
            body += [f"  {goal[:50]}: {count}" for goal, count in stats["top_goals"]]
        return StructuredResult.success("exp", "\n".join(body))

    def _cmd_sensors(self, shell, cmd: Command) -> StructuredResult:
        if self.kernel is None:
            return StructuredResult.failure("sensors", "no kernel bound")
        snapshot = self.kernel.perception.snapshot()
        return StructuredResult.success("sensors", json.dumps(snapshot, default=str, indent=2))


def _input_gen():
    """Generator reading lines from stdin."""
    while True:
        yield input(InteractiveShell.PROMPT)


def parse_scalar(value: str):
    """Coerce a ``k=v`` run argument into a scalar where obvious."""
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def fast_stringify(data) -> str:
    """Compact, readable rendering of capability result payloads."""
    if isinstance(data, dict):
        if "stdout" in data and isinstance(data["stdout"], str):
            return data["stdout"].rstrip("\n")
        parts = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                parts.append(f"{key}={json.dumps(value, default=str)}")
            else:
                parts.append(f"{key}={value}")
        return "\n".join(parts)
    if isinstance(data, (list, tuple)):
        return "\n".join(str(item) for item in data)
    return str(data)