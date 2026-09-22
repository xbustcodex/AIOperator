"""Debian dependency resolution for rootfs construction (stdlib only).

A greedy, correct-enough resolver: given an index of package records, it
selects candidates matching a target architecture and expands the dependency
closure of a seed package set. Handles alternatives (``a | b``), version
constraints and virtual packages (``Provides``).

Not a replacement for apt at runtime; it only computes the closure of the
rootfs base set at build time.
"""

import re
from dataclasses import dataclass
from typing import Optional

_RE_NUMBER = re.compile(r"[0-9]+|[a-zA-Z]+|[.+~-]")


def split_version(version: str) -> tuple[str, str]:
    if ":" in version:
        epoch, _, rest = version.partition(":")
        try:
            int(epoch)
            return epoch, rest
        except ValueError:
            pass
    return "0", version


def vercmp(a: str, b: str) -> int:
    """Compare two Debian version strings (<0, 0, >0)."""
    a_epoch, a_rest = split_version(a)
    b_epoch, b_rest = split_version(b)
    if a_epoch != b_epoch:
        return -1 if int(a_epoch) < int(b_epoch) else 1

    a_up, _, a_down = a_rest.partition("-")
    b_up, _, b_down = b_rest.partition("-")

    result = _cmp_component(a_up, b_up)
    if result != 0:
        return result
    return _cmp_component(a_down, b_down)


def _cmp_component(a: str, b: str) -> int:
    a_parts = _pieces(a)
    b_parts = _pieces(b)
    a_idx = b_idx = 0
    while a_idx < len(a_parts) or b_idx < len(b_parts):
        a_part = a_parts[a_idx] if a_idx < len(a_parts) else None
        b_part = b_parts[b_idx] if b_idx < len(b_parts) else None
        if a_part is None:
            return -1  # a is a prefix of b => a is smaller
        if b_part is None:
            return 1   # b is a prefix of a => a is larger
        a_is_num = a_part.isdigit()
        b_is_num = b_part.isdigit()
        if a_is_num and b_is_num:
            if len(a_part) != len(b_part):
                return 1 if len(a_part) > len(b_part) else -1
            if a_part != b_part:
                return 1 if a_part > b_part else -1
        elif a_is_num:
            return 1
        elif b_is_num:
            return -1
        elif a_part != b_part:
            return 1 if a_part > b_part else -1
        a_idx += 1
        b_idx += 1
    return 0


def _pieces(component: str) -> list[str]:
    return [tok for tok in _RE_NUMBER.findall(component) if tok != ""]


@dataclass
class Constraint:
    name: str
    operator: str = ""
    version: str = ""

    def satisfied_by(self, version: str) -> bool:
        if not self.operator:
            return True
        cmp_result = vercmp(version, self.version)
        return {
            "<": cmp_result < 0,
            "<=": cmp_result <= 0,
            "=": cmp_result == 0,
            ">=": cmp_result >= 0,
            ">": cmp_result > 0,
            "!=": cmp_result != 0,
        }.get(self.operator, True)


def parse_depends(field: str) -> list[list[Constraint]]:
    """Parse a Depends/Pre-Depends field into alternative groups."""
    groups: list[list[Constraint]] = []
    for group in (field or "").split(","):
        group = group.strip()
        if not group:
            continue
        alternatives = [_parse_alternative(a.strip()) for a in group.split("|") if a.strip()]
        groups.append(alternatives)
    return groups


def _parse_alternative(alternative: str) -> Constraint:
    match = re.match(
        r"(?P<name>[A-Za-z0-9+._-]+)"
        r"(?P<arch>:[A-Za-z0-9_-]+)?"
        r"(?:\s*\((?P<op><=|<|>=|>|=|!=)\s*(?P<version>[^)]+)\))?",
        alternative,
    )
    if not match:
        return Constraint(name=alternative)
    return Constraint(
        name=match.group("name"),
        operator=match.group("op") or "",
        version=(match.group("version") or "").strip(),
    )


class DependencyResolver:
    """Resolve the package closure for a rootfs base set."""

    def __init__(self, records: list, architecture: str):
        self.architecture = architecture
        self.candidates: dict[str, list] = {}
        self.providers: dict[str, list] = {}
        for record in records:
            if record.architecture not in (architecture, "all"):
                continue
            self.candidates.setdefault(record.package, []).append(record)
            for virtual in getattr(record, "provides_names", lambda: [])():
                self.providers.setdefault(virtual, []).append(record)

    def available(self, name: str) -> bool:
        return name in self.candidates or name in self.providers

    def resolve(self, seeds: list[str]) -> list:
        """Return chosen PackageRecords in dependency-closure order."""
        chosen: dict[str, object] = {}
        order: list = []
        queue = list(seeds)
        queued: set[str] = set(seeds)

        while queue:
            name = queue.pop(0)
            record = self.pick(name)
            if record is None:
                raise KeyError(f"cannot satisfy dependency: {name}")
            if record.package in chosen:
                continue
            chosen[record.package] = record
            order.append(record)
            for group in parse_depends(record.depends):
                if any(self._satisfied_by_chosen(chosen, alt) for alt in group):
                    continue
                for alt in group:
                    candidate = self.pick(alt.name)
                    if candidate is None:
                        continue
                    if alt.operator and not alt.satisfied_by(candidate.version):
                        continue
                    if candidate.package not in chosen and candidate.package not in queued:
                        queued.add(candidate.package)
                        queue.append(candidate.package)
                    break
        return order

    def pick(self, name: str):
        candidates = self.candidates.get(name, []) or []
        if candidates:
            candidates = sorted(candidates, key=lambda r: r.version, reverse=True)
            return candidates[0]
        for record in self.providers.get(name, []):
            if record.package in self.candidates:
                return record
        return None

    @staticmethod
    def _satisfied_by_chosen(chosen: dict, alt: Constraint) -> bool:
        record = chosen.get(alt.name)
        if record is None:
            return False
        if alt.operator:
            return alt.satisfied_by(record.version)
        return True