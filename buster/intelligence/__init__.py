"""Intelligence layer for Buster OS.

Composes the basal nervous system, cognitive rhythm, attention, expanded
world model, memory coordinator, goals, plans, learning, reflection,
curiosity, agent roles, proactive analysis, self-maintenance, provider
intelligence and cognitive orchestration into ONE bundle that plugs into the
existing Kernel. It introduces no second runtime, scheduler, event system or
agent framework.
"""

import logging
import os

from buster.intelligence.agents import describe_roles
from buster.intelligence.attention import Attention
from buster.intelligence.curiosity import CuriosityEngine
from buster.intelligence.goals import GoalStore
from buster.intelligence.learning import LearningEngine
from buster.intelligence.maintenance import SelfMaintenance
from buster.intelligence.memory import MemoryCoordinator
from buster.intelligence.nervous import NervousSystem
from buster.intelligence.orchestration import CognitiveOrchestrator
from buster.intelligence.plans import PlanStore
from buster.intelligence.proactive import ProactiveEngine
from buster.intelligence.providers import ProviderIntelligence
from buster.intelligence.reflection import ReflectionCoordinator
from buster.intelligence.rhythm import CognitiveRhythm


class IntelligenceBundle:
    """One coherent cognition surface bound to a single Kernel."""

    def __init__(self, kernel):
        self.kernel = kernel
        install_path = kernel.config.install_path
        state_dir = os.path.join(install_path, "state")
        memory_dir = os.path.join(install_path, "memory")
        os.makedirs(state_dir, exist_ok=True)

        self.nervous = NervousSystem(kernel)
        self.rhythm = CognitiveRhythm(kernel)
        self.attention = Attention(kernel)
        self.memory = MemoryCoordinator(
            memory_dir,
            knowledge=kernel.memory.knowledge,
            experience=kernel.memory.experience,
            store=kernel.memory.store,
        )
        self.goals = GoalStore(state_dir)
        self.plans = PlanStore(state_dir)
        self.learning = LearningEngine(kernel, memory_dir)
        self.reflection = ReflectionCoordinator(kernel,
                                                engine=kernel.memory.reflection)
        self.curiosity = CuriosityEngine(kernel)
        self.proactive = ProactiveEngine(kernel, state_dir)
        self.maintenance = SelfMaintenance(kernel)
        self.providers = ProviderIntelligence(kernel)
        self.orchestrator = CognitiveOrchestrator(kernel, cadence=10.0)

        self._started = False
        self.logger = logging.getLogger("buster.intel")

    # -- lifecycle ---------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self.orchestrator.start()
        self.nervous.heed()  # initial awareness pass
        self.logger.info("Intelligence layer online.")
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self.orchestrator.stop()
        self._started = False
        self.logger.info("Intelligence layer offline.")

    # -- observability --------------------------------------------------

    def view(self, section: str) -> dict:
        section = section or "health"
        views = {
            "nervous": lambda: self.nervous.state(),
            "rhythm": lambda: self.rhythm.state(),
            "attention": lambda: self.attention.state(),
            "world": lambda: self.kernel.world_model.snapshot(),
            "memory": lambda: self.memory.stats(),
            "episodic": lambda: {"episodes": self.memory.episodic.recall(limit=10)},
            "procedural": lambda: {"recipes": self.memory.procedural.recipes()},
            "goals": lambda: {"goals": [g.as_dict() for g in self.goals.list_goals()],
                              "stats": self.goals.stats()},
            "plans": lambda: {"plans": [p.as_dict() for p in self.plans.list_plans()]},
            "providers": lambda: self.providers.state(),
            "curiosity": lambda: self.curiosity.state(),
            "reflection": lambda: self.reflection.stats(),
            "suggestions": lambda: {"suggestions": self.proactive.suggestions()},
            "agents": lambda: {"roles": describe_roles()},
            "health": lambda: self.maintenance.diagnostics(),
            "orchestrator": lambda: self.orchestrator.state(),
            "learning": lambda: {"capabilities": self.memory.stats(),
                                 "procedures": self.memory.procedural.recipes()},
        }
        if section not in views:
            return {"error": f"unknown intelligence view '{section}'",
                    "available": sorted(views)}
        return views[section]()


def install_intelligence(kernel) -> IntelligenceBundle:
    """Attach the intelligence layer to a Kernel and return the bundle."""
    kernel.intel = IntelligenceBundle(kernel)
    return kernel.intel


__all__ = ["IntelligenceBundle", "install_intelligence"]