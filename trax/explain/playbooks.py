"""Curated suggestion playbooks by diagnosis."""

from __future__ import annotations


PLAYBOOKS: dict[str, tuple[str, ...]] = {
    "retrieval_grounding_failure": (
        "increase top_k",
        "add reranker",
        "add grounding constraint to prompt",
    ),
    "control_flow_loop": (
        "add explicit retry limit",
        "log loop exit condition inputs",
        "short-circuit repeated failing branch",
    ),
    "latency_degradation": (
        "reduce slow step work or payload size",
        "add timeout or fallback around slow dependency",
        "cache or reuse stable intermediate results",
    ),
    "missing_execution_output": (
        "verify output artifact is written on every successful path",
        "check step error handling before output persistence",
        "inspect interrupted or partial run behavior",
    ),
    "unknown_failure_pattern": (
        "inspect the failing step artifacts and attributes",
    ),
}
