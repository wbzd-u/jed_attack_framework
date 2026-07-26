from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from .baseline import (
    MAX_REPLAY_CANDIDATES,
    baseline_chains,
    fixture_workflow_chains,
    portfolio_chains,
    score_chains,
    source_workflow_chains,
)
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


def _int_env(name: str, default: int, *, lower: int = 0, upper: int = MAX_REPLAY_CANDIDATES) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lower, min(value, upper))


def _float_env(name: str, default: float, *, lower: float = 0.1) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lower, value)


def _optional_int_env(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        return None


def _dedupe_chains(
    *groups: Iterable[Sequence[str]],
    limit: int,
) -> tuple[tuple[str, ...], ...]:
    """Keep deterministic, SDK-valid replay chains while preserving order."""
    result: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for group in groups:
        for raw_messages in group:
            messages = tuple(
                str(message).strip()[:2_000]
                for message in raw_messages
                if isinstance(message, str) and message.strip()
            )[:32]
            if not messages or messages in seen:
                continue
            seen.add(messages)
            result.append(messages)
            if len(result) >= limit:
                return tuple(result)
    return tuple(result)


def _static_portfolio(mode: str, *, limit: int) -> tuple[tuple[str, ...], ...]:
    """Resolve a replay portfolio without running the target agent."""
    canary_count = _int_env("JED_CANARY_COUNT", 24)
    deputy_count = _int_env("JED_DEPUTY_COUNT", 0)
    deputy_batch_size = _int_env("JED_DEPUTY_BATCH_SIZE", 1, lower=1, upper=4)
    fixture_count = _int_env("JED_FIXTURE_COUNT", 0)
    fixture_start = _int_env("JED_FIXTURE_START", 0)
    source_count = _optional_int_env("JED_SOURCE_COUNT")

    if mode == "baseline":
        chains = baseline_chains(
            canary_count=canary_count,
            source_count=source_count,
            limit=limit,
        )
    elif mode == "score":
        chains = score_chains(
            canary_count=canary_count,
            deputy_count=deputy_count,
            deputy_batch_size=deputy_batch_size,
            limit=limit,
        )
    elif mode == "fixture":
        chains = (
            *source_workflow_chains(source_count),
            *fixture_workflow_chains(fixture_count, start=fixture_start),
        )
    elif mode == "portfolio":
        chains = portfolio_chains(
            canary_count=canary_count,
            deputy_count=deputy_count,
            deputy_batch_size=deputy_batch_size,
            fixture_count=fixture_count,
            fixture_start=fixture_start,
            source_count=source_count,
            limit=limit,
        )
    elif mode == "hybrid":
        # Preserve the historical baseline by default.  Opting into deputy or
        # fixture families makes hybrid a full static portfolio instead.
        if deputy_count or fixture_count:
            chains = portfolio_chains(
                canary_count=canary_count,
                deputy_count=deputy_count,
                deputy_batch_size=deputy_batch_size,
                fixture_count=fixture_count,
                fixture_start=fixture_start,
                source_count=source_count,
                limit=limit,
            )
        else:
            chains = baseline_chains(
                canary_count=canary_count,
                source_count=source_count,
                limit=limit,
            )
    else:
        chains = ()
    return _dedupe_chains((item.messages for item in chains), limit=limit)


def _search_portfolio(
    env: Any,
    config: Any,
    sdk: dict[str, Any],
    *,
    limit: int,
) -> tuple[tuple[str, ...], ...]:
    """Run bounded trace-guided search and return confirmed plus observed paths."""
    catalog = ActionCatalog.from_jsonl(_catalog_path())
    if not catalog.actions:
        return ()

    time_budget = float(getattr(config, "time_budget_s", 30.0) or 30.0)
    max_hops = int(getattr(config, "max_tool_hops", 8) or 8)
    default_search_seconds = min(600.0, max(1.0, time_budget * 0.25))
    search_seconds = min(
        _float_env("JED_SEARCH_MAX_SECONDS", default_search_seconds),
        max(0.1, time_budget * 0.85),
    )
    deadline = time.monotonic() + search_seconds
    adapter = EnvAdapter(env, max_tool_hops=max_hops)
    lanes = (
        "EXFILTRATION",
        "UNTRUSTED_TO_ACTION",
        "DESTRUCTIVE_WRITE",
        "CONFUSED_DEPUTY",
    )
    max_steps = max(1, int(getattr(config, "max_steps", 512) or 512))
    max_nodes = _int_env("JED_SEARCH_MAX_NODES", min(512, max_steps), lower=1, upper=4_000)
    beam_width = _int_env("JED_BEAM_WIDTH", 8, lower=1, upper=64)
    max_depth = _int_env("JED_SEARCH_MAX_DEPTH", min(6, max_hops), lower=1, upper=32)
    confirmed: list[tuple[str, ...]] = []
    observed: list[tuple[str, ...]] = []

    for lane_index, lane in enumerate(lanes):
        if time.monotonic() >= deadline:
            break
        remaining_lanes = len(lanes) - lane_index
        lane_deadline = time.monotonic() + max(0.1, (deadline - time.monotonic()) / remaining_lanes)
        search = BeamSearch(
            adapter,
            catalog,
            predicate_fn=sdk.get("eval_predicates"),
            cell_fn=sdk.get("cell_signature"),
            config=SearchConfig(
                max_depth=max_depth,
                beam_width=beam_width,
                max_nodes=max(1, max_nodes // len(lanes)),
                max_candidates=limit,
                minimize=True,
                lane=lane,
            ),
            deadline=lane_deadline,
        )
        findings = search.run()
        # Findings were clean-replayed and minimized; prefer them over raw
        # generation traces while keeping those traces as a separate portfolio.
        confirmed.extend(item.messages for item in findings)
        observed.extend(search.observed_candidate_chains())

    return _dedupe_chains(confirmed, observed, limit=limit)


def build_algorithm_class():
    """Return an SDK-compatible class while keeping offline imports optional."""
    sdk = load_sdk()
    base = sdk.get("AttackAlgorithmBase", object)
    candidate_cls = sdk.get("AttackCandidate")

    class AttackAlgorithm(base):
        def run(self, env: Any, config: Any) -> list[Any]:
            if candidate_cls is None:
                return []

            mode = os.getenv("JED_MODE", "search").strip().lower()
            if mode not in {"baseline", "score", "fixture", "search", "hybrid", "portfolio"}:
                mode = "search"
            limit = _int_env("JED_MAX_CANDIDATES", MAX_REPLAY_CANDIDATES, lower=1)
            static_chains = _static_portfolio(mode, limit=limit)

            if mode in {"baseline", "score", "fixture"}:
                selected = static_chains
            else:
                search_chains = _search_portfolio(env, config, sdk, limit=limit)
                # Regression protection: hybrid/portfolio always retain the
                # static baseline even when the online search finds something.
                # Static chains lead so a replay timeout cannot erase known
                # score coverage; confirmed search paths are still appended.
                selected = _dedupe_chains(static_chains, search_chains, limit=limit)

            return [safe_candidates(candidate_cls, messages) for messages in selected]

    return AttackAlgorithm
