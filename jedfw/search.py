from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .env import EnvAdapter
from .knowledge import ActionCatalog
from .models import Finding, SearchNode, TraceView
from .replay import confirm_finding
from .trace import build_trace_view, cell_key, progress_key, score_cell_key


@dataclass(frozen=True)
class SearchConfig:
    max_depth: int = 6
    beam_width: int = 8
    max_nodes: int = 256
    max_candidates: int = 2000
    minimize: bool = True
    lane: str | None = None
    stagnation_limit: int = 2


def _node_score(view: TraceView, novel: bool, depth: int) -> float:
    predicate_bonus = 1000.0 if view.real_success else 0.0
    action_bonus = 10.0 * len(view.facts & {
        "email_source", "web_source", "secret_read", "share_action",
        "write_action", "exec_action", "protected_write",
    })
    return predicate_bonus + 100.0 * float(novel) + view.score + action_bonus - 2.0 * depth


class BeamSearch:
    """Snapshot-backed, trace-guided beam search.

    Prompt selection is deliberately delegated to ``ActionCatalog``.  This
    lets the framework remain stable while benchmark-specific prompts evolve.
    """

    def __init__(
        self,
        env: EnvAdapter,
        catalog: ActionCatalog,
        *,
        predicate_fn=None,
        cell_fn=None,
        config: SearchConfig | None = None,
        deadline: float | None = None,
    ) -> None:
        self.env = env
        self.catalog = catalog
        self.predicate_fn = predicate_fn
        self.cell_fn = cell_fn
        self.config = config or SearchConfig()
        self.deadline = deadline
        self.archive: set[str] = set()
        self.findings: list[Finding] = []
        # A generation trace can show a successful sensitive tool action even
        # when the local predicate does not fire.  Preserve those *observed*
        # paths separately from confirmed findings so portfolio mode can submit
        # them for evaluator replay without mislabeling them as successes.
        self._observed_candidates: dict[str, SearchNode] = {}

    def _expired(self) -> bool:
        return self.deadline is not None and time.monotonic() >= self.deadline

    def _view(self) -> TraceView:
        return build_trace_view(
            self.env.trace(),
            predicate_fn=self.predicate_fn,
            cell_fn=self.cell_fn,
        )

    def _ordered_actions(self, parent: SearchNode):
        """Order legal primitives from observable state, not prompt position."""
        facts = parent.view.facts
        actions = self.catalog.applicable(facts, lane=self.config.lane)

        if "has_tool_event" not in facts:
            phases = ("source", "bridge", "action", "repair", "any")
        elif {"web_source", "email_source"} & facts and "file_read" not in facts:
            phases = ("bridge", "action", "repair", "source", "any")
        elif "file_read" in facts:
            phases = ("action", "bridge", "repair", "source", "any")
        else:
            phases = ("action", "repair", "bridge", "source", "any")

        rank = {phase: index for index, phase in enumerate(phases)}
        return tuple(
            sorted(
                actions,
                key=lambda action: (rank.get(action.phase, len(rank)), -action.priority, action.name),
            )
        )

    def run(self) -> list[Finding]:
        self.env.reset()
        root_snapshot = self.env.snapshot()
        root_view = self._view()
        frontier = [
            SearchNode(
                messages=(), snapshot=root_snapshot, view=root_view, depth=0,
                lane=self.config.lane or "",
            )
        ]
        seen_messages: set[tuple[str, ...]] = {()}
        nodes = 0

        for depth in range(self.config.max_depth):
            if self._expired() or not frontier or nodes >= self.config.max_nodes:
                break
            children: list[SearchNode] = []

            for parent in frontier:
                if self._expired() or nodes >= self.config.max_nodes:
                    break

                for action in self._ordered_actions(parent):
                    if self._expired() or nodes >= self.config.max_nodes:
                        break
                    if action.text in parent.messages:
                        continue
                    messages = parent.messages + (action.text,)
                    if messages in seen_messages:
                        continue

                    self.env.restore(parent.snapshot)
                    self.env.interact(action.text)
                    view = self._view()
                    nodes += 1
                    seen_messages.add(messages)

                    key = progress_key(view)
                    novel = key not in self.archive
                    self.archive.add(key)
                    stagnant = parent.stagnant_steps + (0 if novel else 1)
                    if stagnant > self.config.stagnation_limit:
                        continue
                    node = SearchNode(
                        messages=messages,
                        snapshot=self.env.snapshot(),
                        view=view,
                        depth=depth + 1,
                        score=_node_score(view, novel, depth + 1),
                        parent_key=cell_key(parent.view),
                        lane=self.config.lane or "",
                        mechanism=",".join(sorted(action.mechanisms)),
                        stagnant_steps=stagnant,
                    )
                    children.append(node)

                    if self._should_harvest(node):
                        self._record_observed_candidate(node)

                    if view.real_success:
                        finding = confirm_finding(
                            self.env,
                            messages,
                            predicate_fn=self.predicate_fn,
                            cell_fn=self.cell_fn,
                            minimize=self.config.minimize,
                        )
                        if finding is not None:
                            self._record_finding(finding)
                            if len(self.findings) >= self.config.max_candidates:
                                break

            children.sort(key=lambda item: item.score, reverse=True)
            frontier = children[: self.config.beam_width]

        return list(self.findings)

    def observed_candidate_chains(self) -> tuple[tuple[str, ...], ...]:
        """Return successful-action traces observed during search generation.

        These are deliberately not ``Finding`` objects: they have not passed a
        clean predicate replay in this environment.  They are useful only as
        bounded, evidence-backed candidates for a different evaluator/model.
        """
        ordered = sorted(
            self._observed_candidates.values(),
            key=lambda node: (
                -self._observed_value(node),
                len(node.messages),
                node.messages,
            ),
        )
        return tuple(node.messages for node in ordered[: self.config.max_candidates])

    @staticmethod
    def _should_harvest(node: SearchNode) -> bool:
        facts = node.view.facts
        # A source-only trace is not a replay candidate: it cannot satisfy a
        # predicate by itself.  Retain only traces with an actually successful
        # sensitive action or a protected read that can inform later replay.
        return bool(
            facts
            & {
                "share_action",
                "write_action",
                "exec_action",
                "secret_read",
                "protected_write",
            }
        )

    @staticmethod
    def _observed_value(node: SearchNode) -> int:
        facts = node.view.facts
        return sum(
            fact in facts
            for fact in (
                "exfiltration",
                "destructive_write",
                "untrusted_to_action",
                "confused_deputy",
                "secret_read",
                "share_action",
                "protected_write",
                "exec_action",
                "write_action",
            )
        )

    def _record_observed_candidate(self, node: SearchNode) -> None:
        # Tool-centric score cells are the relevant diversity unit for the
        # evaluator. Keep a short representative for each observed cell, while
        # retaining separate candidates when the SDK cannot provide a cell key.
        key = score_cell_key(node.view, self.cell_fn)
        if not key:
            key = "messages:" + "\u241f".join(node.messages)
        old = self._observed_candidates.get(key)
        if old is None:
            self._observed_candidates[key] = node
            return
        if self._observed_value(node) > self._observed_value(old):
            self._observed_candidates[key] = node
            return
        if (
            self._observed_value(node) == self._observed_value(old)
            and len(node.messages) < len(old.messages)
        ):
            self._observed_candidates[key] = node

    def _record_finding(self, finding: Finding) -> None:
        identity = (finding.cell_key, finding.messages)
        if any((item.cell_key, item.messages) == identity for item in self.findings):
            return
        self.findings.append(finding)
