from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def load_sdk() -> dict[str, Any]:
    """Load optional competition helpers without making offline tests depend on them."""
    result: dict[str, Any] = {}
    try:
        from aicomp_sdk.attacks.contracts import AttackAlgorithmBase, AttackCandidate
        from aicomp_sdk.core.cells import cell_signature
        from aicomp_sdk.core.predicates import eval_predicates

        result.update(
            AttackAlgorithmBase=AttackAlgorithmBase,
            AttackCandidate=AttackCandidate,
            cell_signature=cell_signature,
            eval_predicates=eval_predicates,
        )
    except Exception:
        return result
    return result


def safe_candidates(candidate_cls: Any, messages: Sequence[str]) -> Any:
    if hasattr(candidate_cls, "from_messages"):
        return candidate_cls.from_messages(tuple(messages))
    return candidate_cls(user_messages=tuple(messages))
