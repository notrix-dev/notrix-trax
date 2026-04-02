"""Curated suggestion playbooks by diagnosis."""

from __future__ import annotations

from trax.explain.models import Diagnosis

PLAYBOOKS: dict[Diagnosis, tuple[str, ...]] = {
    Diagnosis.RETRIEVAL_GROUNDING_FAILURE: (
        "increase top_k",
        "add reranker",
        "add grounding constraint to prompt",
    ),
    Diagnosis.CONTROL_FLOW_LOOP: (
        "add explicit retry limit",
        "log loop exit condition inputs",
        "short-circuit repeated failing branch",
    ),
    Diagnosis.LATENCY_DEGRADATION: (
        "reduce slow step work or payload size",
        "add timeout or fallback around slow dependency",
        "cache or reuse stable intermediate results",
    ),
    Diagnosis.MISSING_EXECUTION_OUTPUT: (
        "verify output artifact is written on every successful path",
        "check step error handling before output persistence",
        "inspect interrupted or partial run behavior",
    ),
    Diagnosis.UNKNOWN_FAILURE_PATTERN: (
        "inspect the failing step artifacts and attributes",
    ),
}
