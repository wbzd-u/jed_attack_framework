"""Reusable, benchmark-facing primitives for deterministic JED attack search.

The package intentionally does not contain benchmark prompts.  Prompts and
mechanism records live in ``knowledge/`` and are injected through a catalog.
"""

from .models import ActionPrimitive, Finding, MechanismCard, SearchNode, TraceView
from .trace import build_trace_view
from .diagnostics import ActionDiagnosis, diagnose_trace

__all__ = [
    "ActionPrimitive",
    "Finding",
    "MechanismCard",
    "SearchNode",
    "TraceView",
    "ActionDiagnosis",
    "build_trace_view",
    "diagnose_trace",
]
