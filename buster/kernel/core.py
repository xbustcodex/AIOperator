"""Kernel core for Buster OS.

The kernel owns the lifecycle of the whole environment: it initialises the
single EventRouter, Scheduler, Permissions, WorldModel, AgentManager and
Audit subsystems, then wires the capability registry, AI providers, memory
stores, perception sensors and security managers on top. There is exactly
one Kernel instance per process.
"""

import logging
import os
from typing import Optional

from buster.ai_providers.local import LocalProvider
from buster.ai_providers.registry import AIProviderRegistry
from buster.ai_providers.remote import RemoteProvider
from buster.capabilities.impl import CORE_CAPABILITIES
from buster.capabilities.registry import CapabilityRegistry
from buster.config import Config
from buster.kernel.agent_manager import AgentManager
from buster.kernel.audit import Audit
from buster.kernel.event_router import EventRouter
from buster.kernel.permissions import Permissions
from buster.kernel.scheduler import Scheduler
from buster.kernel.world_model import WorldModel
from buster.logging import setup_logging
from buster.memory.experience import ExperienceMemory
from buster.memory.knowledge import KnowledgeMemory
from buster.memory.reflection import ReflectionEngine
from buster.perception.base import SensorHub
from buster.perception.device import DeviceSensor
from buster.perception.environment import EnvironmentSensor
from buster.security.elevation import ElevationManager
from buster.security.protection import DeleteProtection
from buster.version import get_version


class Kernel:
    """Lifecycle controller owning all core subsystems."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.state = "created"
        self.runtime_lock = None  # set by RuntimeServer when running as daemon

        # -- core control plane -------------------------------------
        self.event_router = EventRouter()
        self.scheduler = Scheduler()
        self.permissions = Permissions(persist=self._persist_permissions)
        self.world_model = WorldModel(event_router=self.event_router)
        self.agent_manager = AgentManager(event_router=self.event_router)

        install_path = self.config.get("install_path", os.path.expanduser("~/.buster/"))
        log_dir = os.path.join(install_path, "logs")
        self.audit = Audit(log_dir)

        self._load_permissions()

        # -- security -----------------------------------------------
        self.security = SecurityBundle(
            config=self.config,
            protection=DeleteProtection(self._default_protected()),
            elevation=ElevationManager(
                approval=lambda action, ctx: self._default_approval(action, ctx),
            ),
        )

        # -- capabilities -------------------------------------------
        self.cap = CapabilityRegistry(kernel=self)
        for capability_cls in CORE_CAPABILITIES:
            self.cap.register(capability_cls(kernel=self))

        # -- AI providers -------------------------------------------
        self.ai = AISubsystem(config=self.config)
        self.ai.providers.register(LocalProvider(), default=True)
        self._register_remote_provider()

        # -- memory -------------------------------------------------
        memory_dir = os.path.join(install_path, "memory")
        self.memory = MemorySubsystem(
            memory_dir=memory_dir,
            experience=ExperienceMemory(memory_dir),
            knowledge=KnowledgeMemory(memory_dir),
        )
        self.memory.reflection = ReflectionEngine(knowledge=self.memory.knowledge)

        # -- perception ---------------------------------------------
        self.perception = SensorHub()
        self.perception.register(DeviceSensor())
        self.perception.register(EnvironmentSensor())

        self.logger = logging.getLogger("buster.kernel.core")

    # -- lifecycle -----------------------------------------------------

    def start(self) -> None:
        if self.state == "running":
            return
        self.state = "starting"
        install_path = self.config.get("install_path", os.path.expanduser("~/.buster/"))
        self.logger.info("Buster OS kernel %s starting", get_version())

        setup_logging(os.path.join(install_path, "logs"),
                      self.config.get("logging_level", "INFO"))

        self.event_router.start()
        self.world_model.set_fact("buster.version", get_version())
        self.world_model.set_fact("capabilities", self.cap.list_capabilities())
        self.world_model.component_status("kernel", "starting")
        self.scheduler.start()
        self.world_model.component_status("event_router", "running")
        self.world_model.component_status("scheduler", "running")
        self.world_model.component_status("kernel", "running")

        self.state = "running"
        self.event_router.emit("kernel.started", {"version": get_version()})
        self.audit.record("kernel.start", "kernel", {"version": get_version()})
        self.logger.info("Buster OS kernel running.")

    def stop(self) -> None:
        if self.state == "stopped":
            return
        self.state = "stopping"
        self.logger.info("Buster OS kernel stopping")

        self.agent_manager.shutdown_all()
        self.scheduler.stop()

        self.world_model.component_status("kernel", "stopped")
        self.audit.record("kernel.stop", "kernel")
        self.event_router.stop()

        try:
            self.memory.reflection.reflect(self.memory.experience.recall(limit=20))
        except Exception:  # noqa: BLE001
            self.logger.exception("Reflection during shutdown failed")

        self.cap.shutdown()
        self.perception.shutdown()
        self.ai.providers.shutdown()

        if self.runtime_lock is not None:
            self.runtime_lock.release()

        self.state = "stopped"
        self.logger.info("Buster OS kernel stopped.")

    # -- permission helpers ---------------------------------------------

    def require(self, action: str, scope: Optional[str] = None,
                context: Optional[dict] = None) -> None:
        """Gate an action through the kernel permission system."""
        self.permissions.require(action, scope, context)

    # -- permission persistence ---------------------------------------

    def _load_permissions(self) -> None:
        rules = self.config.get_nested("permissions.rules", None)
        if isinstance(rules, list):
            self.permissions.from_rules(rules)

    def _persist_permissions(self, rules: list[dict]) -> None:
        self.config.set_nested("permissions.rules", rules)

    # -- convenience accessors ----------------------------------------

    def status(self) -> dict:
        return {
            "state": self.state,
            "version": get_version(),
            "event_router_running": self.event_router.running,
            "scheduler_running": self.scheduler.running,
            "capabilities": self.cap.list_capabilities(),
            "ai_providers": self.ai.providers.names(),
            "agents": [a.name for a in self.agent_manager.list_agents()],
            "jobs": [{"name": j.name, "status": j.status.value} for j in self.scheduler.list_jobs()],
        }

    # -- internal helpers ----------------------------------------------

    def _default_protected(self) -> list[str]:
        install_path = self.config.get("install_path", os.path.expanduser("~/.buster/"))
        return [
            install_path.rstrip(os.sep) + os.sep,
            os.path.join(install_path, "config"),
            os.path.join(install_path, "memory"),
            os.path.join(install_path, "logs"),
            os.path.join(install_path, "state"),
        ]

    def _default_approval(self, action: str, context: dict) -> bool:
        """Scripted elevation approval: only actions pre-granted in config."""
        allowed = self.config.get_nested("security.elevation_allow", []) or []
        approved = action in allowed
        if approved:
            self.audit.record("elevation.approved", context.get("actor", "unknown"),
                              {"action": action})
        else:
            self.audit.record("elevation.denied", context.get("actor", "unknown"),
                              {"action": action})
        return approved

    def _register_remote_provider(self) -> None:
        providers = self.config.get("ai_providers", {}) or {}
        if "remote" in providers:
            remote_cfg = providers["remote"]
            api_key = remote_cfg.get("api_key", "")
            if api_key:
                self.ai.providers.register(RemoteProvider(
                    api_key=api_key,
                    base_url=remote_cfg.get("base_url", "https://api.openai.com/v1"),
                    model=remote_cfg.get("model", ""),
                ))
                self.logger.info("Remote AI provider configured.")


class SecurityBundle:
    """Groups security managers for capability enforcement."""

    def __init__(self, config, protection: DeleteProtection, elevation: ElevationManager):
        self.config = config
        self.protection = protection
        self.elevation = elevation


class AISubsystem:
    """AI providers plus agent helpers."""

    def __init__(self, config: Config):
        self.config = config
        self.providers = AIProviderRegistry()


class MemorySubsystem:
    """All memory stores behind one handle."""

    def __init__(self, memory_dir: str, experience: ExperienceMemory, knowledge: KnowledgeMemory):
        self.memory_dir = memory_dir
        self.experience = experience
        self.knowledge = knowledge
        from buster.memory.core import Memory
        self.store = Memory(memory_dir)

    def snapshot(self) -> dict:
        return {
            "store_keys": self.store.keys(),
            "experience_count": self.experience.count(),
            "knowledge_keys": self.knowledge.keys(),
        }