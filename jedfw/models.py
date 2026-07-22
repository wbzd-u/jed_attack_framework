from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ActionPrimitive:
    """A composable user-message action.

    ``requires`` and ``produces`` are abstract state facts, not tool names.
    This keeps the searcher independent from any particular prompt library.
    """

    name: str
    phase: str
    text: str
    requires: frozenset[str] = frozenset()
    produces: frozenset[str] = frozenset()
    mechanisms: frozenset[str] = frozenset()
    predicates: frozenset[str] = frozenset()
    priority: float = 0.0
    enabled: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ActionPrimitive":
        def as_set(key: str) -> frozenset[str]:
            raw = value.get(key, ())
            if isinstance(raw, str):
                raw = (raw,)
            return frozenset(str(item) for item in raw or ())

        return cls(
            name=str(value.get("name", "unnamed")),
            phase=str(value.get("phase", "any")),
            text=str(value.get("text", "")).strip(),
            requires=as_set("requires"),
            produces=as_set("produces"),
            mechanisms=as_set("mechanisms"),
            predicates=as_set("predicates"),
            priority=float(value.get("priority", 0.0)),
            enabled=bool(value.get("enabled", True)),
        )


@dataclass(frozen=True)
class MechanismCard:
    """A transferable hypothesis extracted from a prior experiment."""

    name: str
    target_layer: str = ""
    carrier: str = ""
    preconditions: tuple[str, ...] = ()
    transitions: tuple[str, ...] = ()
    operators: tuple[str, ...] = ()
    predicates: tuple[str, ...] = ()
    failure_boundaries: tuple[str, ...] = ()
    transferability: str = "unknown"
    source_case: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MechanismCard":
        def as_tuple(key: str) -> tuple[str, ...]:
            raw = value.get(key, ())
            if isinstance(raw, str):
                raw = (raw,)
            return tuple(str(item) for item in raw or ())

        return cls(
            name=str(value.get("name", value.get("mechanism", "unnamed"))),
            target_layer=str(value.get("target_layer", "")),
            carrier=str(value.get("carrier", "")),
            preconditions=as_tuple("preconditions"),
            transitions=as_tuple("transitions"),
            operators=as_tuple("operators"),
            predicates=as_tuple("predicates"),
            failure_boundaries=as_tuple("failure_boundaries"),
            transferability=str(value.get("transferability", "unknown")),
            source_case=str(value.get("source_case", value.get("id", ""))),
        )


@dataclass(frozen=True)
class TraceView:
    """Normalized, evidence-oriented view of an environment trace."""

    raw: Mapping[str, Any]
    events: tuple[Mapping[str, Any], ...]
    messages: tuple[str, ...]
    predicates: tuple[Mapping[str, Any], ...]
    cell: Mapping[str, Any]
    facts: frozenset[str]
    score: float = 0.0

    @property
    def successful_tools(self) -> tuple[str, ...]:
        return tuple(
            str(event.get("name", ""))
            for event in self.events
            if event.get("ok", True) is True
        )

    @property
    def successful_events(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(event for event in self.events if event.get("ok", True) is True)

    @property
    def real_success(self) -> bool:
        return bool(self.predicates)


@dataclass(frozen=True)
class SearchNode:
    """A restorable frontier point in the search tree."""

    messages: tuple[str, ...]
    snapshot: Any
    view: TraceView
    depth: int
    score: float = 0.0
    parent_key: str = ""
    lane: str = ""
    mechanism: str = ""
    stagnant_steps: int = 0


@dataclass(frozen=True)
class Finding:
    messages: tuple[str, ...]
    trace: TraceView
    predicate_names: tuple[str, ...]
    cell_key: str
    score_cell_key: str = ""
    replay_confirmed: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
