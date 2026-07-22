from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .env import EnvAdapter
from .models import Finding
from .trace import build_trace_view, cell_key, score_cell_key


def replay(
    env: EnvAdapter,
    messages: Sequence[str],
    *,
    predicate_fn=None,
    cell_fn=None,
):
    env.reset()
    for message in messages:
        env.interact(message)
    trace = env.trace()
    return build_trace_view(trace, predicate_fn=predicate_fn, cell_fn=cell_fn)


def minimize_messages(
    env: EnvAdapter,
    messages: Sequence[str],
    *,
    predicate_fn=None,
    cell_fn=None,
) -> tuple[str, ...]:
    """Greedy delta debugging against a clean reset for each trial."""
    current = list(messages)
    changed = True
    while changed and len(current) > 1:
        changed = False
        for index in range(len(current)):
            trial = current[:index] + current[index + 1 :]
            view = replay(env, trial, predicate_fn=predicate_fn, cell_fn=cell_fn)
            if view.real_success:
                current = trial
                changed = True
                break
    return tuple(current)


def confirm_finding(
    env: EnvAdapter,
    messages: Sequence[str],
    *,
    predicate_fn=None,
    cell_fn=None,
    minimize: bool = True,
) -> Finding | None:
    current = tuple(messages)
    view = replay(env, current, predicate_fn=predicate_fn, cell_fn=cell_fn)
    if not view.real_success:
        return None
    if minimize:
        current = minimize_messages(env, current, predicate_fn=predicate_fn, cell_fn=cell_fn)
        view = replay(env, current, predicate_fn=predicate_fn, cell_fn=cell_fn)
    names = tuple(sorted({str(item.get("predicate", "")) for item in view.predicates}))
    return Finding(
        messages=current,
        trace=view,
        predicate_names=names,
        cell_key=cell_key(view),
        score_cell_key=score_cell_key(view, cell_fn),
        replay_confirmed=True,
    )
