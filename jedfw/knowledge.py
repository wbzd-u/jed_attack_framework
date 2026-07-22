from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import ActionPrimitive, MechanismCard


def load_jsonl(path: str | Path, factory):
    """Load tolerant JSONL; malformed rows are skipped and reported by caller."""
    result = []
    source = Path(path)
    if not source.exists():
        return result
    for line in source.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(factory(value))
        except (OSError, TypeError, ValueError):
            continue
    return result


class ActionCatalog:
    def __init__(self, actions: Iterable[ActionPrimitive] = ()) -> None:
        # The SDK enforces MAX_USER_MESSAGE_CHARS=2_000. Reject overlong
        # records rather than silently truncating a prompt's semantics.
        self.actions = tuple(
            action
            for action in actions
            if action.enabled and action.text and len(action.text) <= 2_000
        )

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "ActionCatalog":
        return cls(load_jsonl(path, ActionPrimitive.from_mapping))

    def applicable(
        self,
        facts: frozenset[str],
        *,
        phase: str | None = None,
        lane: str | None = None,
    ) -> tuple[ActionPrimitive, ...]:
        values = [
            action
            for action in self.actions
            if action.requires <= facts and (phase is None or action.phase in {phase, "any"})
            and (lane is None or not action.predicates or lane in action.predicates)
        ]
        return tuple(sorted(values, key=lambda item: item.priority, reverse=True))


class MechanismMemory:
    def __init__(self, cards: Iterable[MechanismCard] = ()) -> None:
        self.cards = tuple(cards)

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "MechanismMemory":
        return cls(load_jsonl(path, MechanismCard.from_mapping))

    def applicable(self, *, predicate: str | None = None, carrier: str | None = None) -> tuple[MechanismCard, ...]:
        values = []
        for card in self.cards:
            if predicate and card.predicates and predicate not in card.predicates:
                continue
            if carrier and card.carrier and carrier != card.carrier:
                continue
            values.append(card)
        return tuple(values)
