"""Deterministic failure-to-diagnosis mapping rules."""

from __future__ import annotations

from trax.models import Failure, FailureKind


def diagnosis_for_failure(failure: Failure) -> tuple[str, tuple[str, ...]]:
    """Map a failure to a diagnosis and likely-cause list."""
    if failure.kind == FailureKind.EMPTY_RETRIEVAL:
        return (
            "retrieval_grounding_failure",
            (
                "low retrieval relevance",
                "insufficient document coverage",
            ),
        )
    if failure.kind == FailureKind.LOOP_DETECTED:
        return (
            "control_flow_loop",
            (
                "repeated step retry pattern",
                "missing exit condition or retry cap",
            ),
        )
    if failure.kind == FailureKind.LATENCY_ANOMALY:
        return (
            "latency_degradation",
            (
                "slow external dependency or model call",
                "excessive work in one step or run path",
            ),
        )
    if failure.kind == FailureKind.MISSING_OUTPUT:
        return (
            "missing_execution_output",
            (
                "step did not persist expected output",
                "run completed with incomplete artifacts",
            ),
        )
    return (
        "unknown_failure_pattern",
        (
            "detected issue does not yet have a specialized diagnosis",
        ),
    )
