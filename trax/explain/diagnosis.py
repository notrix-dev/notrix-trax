# Copyright 2026 Notrix LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Deterministic failure-to-diagnosis mapping rules."""

from __future__ import annotations

from trax.models import Failure, FailureKind
from trax.explain.models import Diagnosis


def diagnosis_for_failure(failure: Failure) -> tuple[Diagnosis, tuple[str, ...]]:
    """Map a failure to a diagnosis and likely-cause list."""
    if failure.kind == FailureKind.EMPTY_RETRIEVAL:
        return (
            Diagnosis.RETRIEVAL_GROUNDING_FAILURE,
            (
                "low retrieval relevance",
                "insufficient document coverage",
            ),
        )
    if failure.kind == FailureKind.LOOP_DETECTED:
        return (
            Diagnosis.CONTROL_FLOW_LOOP,
            (
                "repeated step retry pattern",
                "missing exit condition or retry cap",
            ),
        )
    if failure.kind == FailureKind.LATENCY_ANOMALY:
        return (
            Diagnosis.LATENCY_DEGRADATION,
            (
                "slow external dependency or model call",
                "excessive work in one step or run path",
            ),
        )
    if failure.kind == FailureKind.MISSING_OUTPUT:
        return (
            Diagnosis.MISSING_EXECUTION_OUTPUT,
            (
                "step did not persist expected output",
                "run completed with incomplete artifacts",
            ),
        )
    return (
        Diagnosis.UNKNOWN_FAILURE_PATTERN,
        (
            "detected issue does not yet have a specialized diagnosis",
        ),
    )
