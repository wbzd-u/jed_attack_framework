from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .env import EnvAdapter
from .knowledge import ActionCatalog
from .sdk import load_sdk, safe_candidates
from .search import BeamSearch, SearchConfig


def _catalog_path() -> Path:
    override = os.getenv("JED_ACTIONS_PATH")
    if override:
        return Path(override)
    here = Path(__file__).resolve().parent.parent
    return here / "knowledge" / "jed_actions.jsonl"


def build_algorithm_class():
    """Return an SDK-compatible class while keeping offline imports optional."""
    sdk = load_sdk()
    base = sdk.get("AttackAlgorithmBase", object)
    candidate_cls = sdk.get("AttackCandidate")

    class AttackAlgorithm(base):
        def run(self, env: Any, config: Any) -> list[Any]:
            if candidate_cls is None:
                return []

            catalog = ActionCatalog.from_jsonl(_catalog_path())
            if not catalog.actions:
                return []

            time_budget = float(getattr(config, "time_budget_s", 30.0) or 30.0)
            max_hops = int(getattr(config, "max_tool_hops", 8) or 8)
            adapter = EnvAdapter(env, max_tool_hops=max_hops)
            # Leave a small safety margin for final replay/minimization.
            import time

            deadline = time.monotonic() + max(0.1, time_budget * 0.85)
            findings = []
            for lane in (
                "EXFILTRATION",
                "UNTRUSTED_TO_ACTION",
                "DESTRUCTIVE_WRITE",
                "CONFUSED_DEPUTY",
            ):
                if time.monotonic() >= deadline:
                    break
                search = BeamSearch(
                    adapter,
                    catalog,
                    predicate_fn=sdk.get("eval_predicates"),
                    cell_fn=sdk.get("cell_signature"),
                    config=SearchConfig(
                        max_depth=min(6, int(getattr(config, "max_tool_hops", 8) or 8)),
                        beam_width=8,
                        max_nodes=min(512, int(getattr(config, "max_steps", 512) or 512)),
                        max_candidates=2000,
                        minimize=True,
                        lane=lane,
                    ),
                    deadline=deadline,
                )
                findings.extend(search.run())

            # The scorer cell is tool-centric. Keep the shortest candidate for
            # each score cell, while allowing richer diagnostic cells internally.
            selected = {}
            for item in findings:
                key = item.score_cell_key or item.cell_key
                old = selected.get(key)
                if old is None or len(item.messages) < len(old.messages):
                    selected[key] = item
            ordered = sorted(
                selected.values(),
                key=lambda item: (-len(item.predicate_names), len(item.messages)),
            )
            return [safe_candidates(candidate_cls, item.messages) for item in ordered[:2000]]

    return AttackAlgorithm
