"""Structured explanation engine result models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Diagnosis(StrEnum):
    RETRIEVAL_GROUNDING_FAILURE = "retrieval_grounding_failure"
    CONTROL_FLOW_LOOP = "control_flow_loop"
    LATENCY_DEGRADATION = "latency_degradation"
    MISSING_EXECUTION_OUTPUT = "missing_execution_output"
    UNKNOWN_FAILURE_PATTERN = "unknown_failure_pattern"


@dataclass(frozen=True)
class Explanation:
    run_id: str
    failure_id: str
    diagnosis: Diagnosis
    step_id: str | None
    likely_causes: tuple[str, ...]
    suggestions: tuple[str, ...]


@dataclass(frozen=True)
class ExplanationResult:
    run_id: str
    explanations: tuple[Explanation, ...]
