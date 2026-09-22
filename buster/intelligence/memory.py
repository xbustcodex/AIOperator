"""Expanded memory architecture for Buster OS.

Adds working (short-term/context), episodic and procedural memory classes and
a MemoryCoordinator that retrieves relevant memories across stores, runs
bounded consolidation, and reports memory statistics.

The existing Memory (key/value), KnowledgeMemory (semantic) and
ExperienceMemory remain the underlying authorities for their domains; this
layer composes them without replacing their APIs.
"""

import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional


# --------------------------------------------------------------------------
# Working memory (short-term context)
# --------------------------------------------------------------------------


@dataclass
class WorkingItem:
    key: str
    content: Any
    ts: float = field(default_factory=time.time)
    ttl: float = 300.0

    def expired(self) -> bool:
        return time.time() - self.ts > self.ttl


class WorkingMemory:
    """Bounded, TTL-scoped short-term working store."""

    def __init__(self, capacity: int = 48, default_ttl: float = 600.0):
        self._items: deque[WorkingItem] = deque(maxlen=capacity)
        self._default_ttl = default_ttl

    def put(self, key: str, content: Any, ttl: Optional[float] = None) -> None:
        self._items.append(WorkingItem(key, content, ttl=ttl or self._default_ttl))

    def get(self, key: str, default: Any = None) -> Any:
        for item in self._items:
            if item.key == key and not item.expired():
                return item.content
        return default

    def context(self, limit: int = 12) -> list[dict]:
        return [{"key": i.key, "content": i.content, "ts": i.ts}
                for i in list(self._items)[-limit:] if not i.expired()]

    def prune_expired(self) -> int:
        kept = [i for i in self._items if not i.expired()]
        pruned = len(self._items) - len(kept)
        self._items = deque(kept, maxlen=self._items.maxlen)
        return pruned


# --------------------------------------------------------------------------
# Episodic memory (bounded appending record of meaningful episodes)
# --------------------------------------------------------------------------


class EpisodicMemory:
    """Appends structured episodes (JSONL) for later recall/consolidation."""

    def __init__(self, memory_dir: str, capacity: int = 2000):
        self._path = os.path.join(memory_dir, "episodic.jsonl")
        self._capacity = capacity
        os.makedirs(memory_dir, exist_ok=True)

    def record(self, title: str, kind: str = "episode", summary: str = "",
               outcome: Optional[str] = None, links: Optional[list] = None,
               detail: Optional[dict] = None) -> None:
        row = {"ts": time.time(), "title": title, "kind": kind,
               "summary": summary, "outcome": outcome,
               "links": links or [], "detail": detail or {}}
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        self._trim()

    def recall(self, limit: int = 20, kind: Optional[str] = None) -> list[dict]:
        entries = self._read()
        if kind:
            entries = [e for e in entries if e.get("kind") == kind]
        entries.sort(key=lambda e: e.get("ts", 0))
        return entries[-limit:]

    def stats(self) -> dict:
        entries = self._read()
        kinds = {}
        for entry in entries:
            kinds[entry.get("kind", "episode")] = kinds.get(entry.get("kind", "episode"), 0) + 1
        return {"count": len(entries), "kinds": kinds}

    def _read(self) -> list[dict]:
        if not os.path.isfile(self._path):
            return []
        entries = []
        with open(self._path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except ValueError:
                        continue
        return entries

    def _trim(self) -> None:
        entries = self._read()
        if len(entries) <= self._capacity:
            return
        with open(self._path, "w", encoding="utf-8") as handle:
            for row in entries[-self._capacity:]:
                handle.write(json.dumps(row) + "\n")


# --------------------------------------------------------------------------
# Procedural memory (recipes / steps) with reliability counters
# --------------------------------------------------------------------------


@dataclass
class Recipe:
    name: str
    steps: list[str]
    uses: int = 0
    successes: int = 0
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    @property
    def reliability(self) -> float:
        return self.successes / self.uses if self.uses else 0.0


class ProceduralMemory:
    """JSON-backed recipe store (procedural knowledge)."""

    def __init__(self, memory_dir: str):
        self._path = os.path.join(memory_dir, "procedural.json")
        self._recipes: dict[str, Recipe] = {}
        os.makedirs(memory_dir, exist_ok=True)
        self._load()

    def learn_recipe(self, name: str, steps: list[str]) -> None:
        self._recipes[name] = Recipe(name=name, steps=steps)
        self._save()

    def record_use(self, name: str, success: bool) -> None:
        recipe = self._recipes.get(name)
        if recipe is None:
            return
        recipe.uses += 1
        if success:
            recipe.successes += 1
        recipe.updated = time.time()
        self._save()

    def recipes(self) -> list[dict]:
        return [{"name": r.name, "steps": r.steps, "uses": r.uses,
                 "successes": r.successes, "reliability": round(r.reliability, 3)}
                for r in self._recipes.values()]

    def _load(self) -> None:
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                rows = json.load(handle)
            for row in rows:
                self._recipes[row["name"]] = Recipe(
                    name=row["name"], steps=row.get("steps", []),
                    uses=row.get("uses", 0), successes=row.get("successes", 0),
                    created=row.get("created", time.time()),
                    updated=row.get("updated", time.time()))
        except (ValueError, OSError):
            self._recipes = {}

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump([r.__dict__ for r in self._recipes.values()], handle, indent=2)


# --------------------------------------------------------------------------
# Coordinator
# --------------------------------------------------------------------------

RECALL_LIMITS = {"working": 8, "episodic": 6, "knowledge": 8, "experience": 4, "procedural": 4}


class MemoryCoordinator:
    """Composes the memory classes into one retrieval/consolidation surface."""

    def __init__(self, memory_dir: str, knowledge=None, experience=None,
                 store=None):
        self.memory_dir = memory_dir
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory(memory_dir)
        self.procedural = ProceduralMemory(memory_dir)
        self.knowledge = knowledge
        self.experience = experience
        self.store = store

    # -- retrieval ------------------------------------------------------

    def retrieve(self, query: str, limit: int = 16) -> list[dict]:
        """Rank relevant memories across stores for a reasoning context."""
        results: list[dict] = []
        lowered = query.lower()
        tokens = {w for w in lowered.split() if len(w) > 2}

        for item in self.working.context(20):
            blob = f"{item['key']} {item['content']}".lower()
            if _overlap(tokens, blob):
                results.append({"store": "working", "score": 4.0, "key": item["key"],
                                "content": item["content"], "ts": item["ts"]})

        for entry in self.episodic.recall(30):
            blob = f"{entry['title']} {entry.get('summary', '')}".lower()
            if _overlap(tokens, blob):
                results.append({"store": "episodic", "score": 3.0, "key": entry["title"],
                                "content": entry.get("summary", ""), "ts": entry["ts"]})

        if self.knowledge is not None:
            for entry in self.knowledge.search("", limit=40):
                blob = f"{entry['key']} {entry['value']}".lower()
                if _overlap(tokens, blob):
                    results.append({"store": "knowledge", "score": 3.0 + entry['confidence'],
                                    "key": entry["key"], "content": entry['value'],
                                    "ts": entry.get("updated", 0)})

        if self.experience is not None:
            for entry in self.experience.recall(30):
                blob = f"{entry.get('target', '')}".lower()
                if _overlap(tokens, blob):
                    results.append({"store": "experience", "score": 2.0,
                                    "key": entry.get("target", ""), "content": entry.get("status", ""),
                                    "ts": entry.get("ts", 0)})

        for recipe in self.procedural.recipes():
            blob = f"{recipe['name']} {' '.join(recipe['steps'])}".lower()
            if _overlap(tokens, blob):
                results.append({"store": "procedural", "score": 2.0 + recipe["reliability"],
                                "key": recipe["name"], "content": recipe["steps"], "ts": 0})

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]

    # -- consolidation -------------------------------------------------------

    def consolidate(self, max_lessons: int = 10) -> dict:
        """Scheduled/event-driven consolidation. Deterministic and bounded."""
        report = {
            "working_pruned": self.working.prune_expired(),
            "episodic_summaries": 0,
            "lessons_promoted": 0,
            "duplicates_merged": 0,
            "contradictions": 0,
            "pruned_knowledge": 0,
            "expired_store_entries": 0,
        }

        # summarize related experiences into episodic memories
        if self.experience is not None:
            seen: dict[str, list] = {}
            for entry in self.experience.recall(50)[-50:]:
                target = entry.get("target", "")[:60]
                if not target:
                    continue
                seen.setdefault(target, []).append(entry)
            promotion = 0
            for target, entries in list(seen.items()):
                if promotion >= max_lessons:
                    break
                done = sum(1 for e in entries if e.get("status") == "done")
                failed = sum(1 for e in entries if e.get("status") == "failed")
                if len(entries) >= 2:
                    self.episodic.record(
                        title=f"summary:{target}", kind="summary",
                        summary=f"{len(entries)} runs ({done} done, {failed} failed)",
                        outcome="mixed" if failed else "done",
                        detail={"target": target, "runs": len(entries)})
                    promotion += 1
            report["episodic_summaries"] = promotion

        # promote lessons to knowledge and merge duplicates
        if self.knowledge is not None:
            lessons = self.knowledge.search("lesson:", limit=30)
            for entry in lessons:
                if entry["confidence"] >= 0.5:
                    report["lessons_promoted"] += 1
            report["pruned_knowledge"] = self._prune_low_value_knowledge()
            report["contradictions"] = self._find_contradictions()

        if self.store is not None and hasattr(self.store, "prune_expired"):
            report["expired_store_entries"] = self.store.prune_expired()

        return report

    def _prune_low_value_knowledge(self) -> int:
        pruned = 0
        if self.knowledge is None or not hasattr(self.knowledge, "_entries"):
            return 0
        now = time.time()
        removable = []
        for key, entry in self.knowledge._entries.items():
            stale = now - entry.updated > 30 * 86400
            if key.startswith("goal_seen:") and entry.confidence < 0.4 and stale:
                removable.append(key)
            if key.startswith("avoid_repeat:") and entry.confidence < 0.3 and stale:
                removable.append(key)
        for key in removable:
            del self.knowledge._entries[key]
            pruned += 1
        if pruned:
            self.knowledge._save()
        return pruned

    def _find_contradictions(self) -> int:
        """Detect when a learned ``pattern`` is contradicted by recent failure."""
        if self.knowledge is None or self.experience is None:
            return 0
        recent_failures: dict[str, list] = {}
        for entry in self.experience.recall(limit=100):
            target = entry.get("target", "") or ""
            if entry.get("status") == "failed" and target:
                recent_failures.setdefault(target[:60], []).append(entry)
        contradictions = 0
        for entry in self.knowledge.search("pattern:", limit=50):
            target = (entry["key"].split(":", 1)[1] if ":" in entry["key"]
                      else entry["key"])[:60]
            failures = recent_failures.get(target, [])
            if failures and not any(e.get("status") == "done" for e in failures):
                self.knowledge.learn(
                    f"contradiction:{target[:50]}",
                    "learned pattern contradicts recent failures",
                    source="consolidation", confidence=0.9)
                contradictions += 1
        return contradictions

    # -- diagnostics ---------------------------------------------------------

    def stats(self) -> dict:
        return {
            "working": len(self.working.context()),
            "episodic": self.episodic.stats(),
            "procedural": [r["name"] for r in self.procedural.recipes()],
            "knowledge_keys": self.knowledge.keys() if self.knowledge else [],
            "experience_count": self.experience.count() if self.experience else 0,
        }


def _overlap(tokens: set[str], blob: str) -> bool:
    return any(token in blob for token in tokens) if tokens else False