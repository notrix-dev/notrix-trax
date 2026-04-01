"""Enum compatibility tests for persisted model constants."""

from __future__ import annotations

from trax.explain.models import Diagnosis
from trax.models import EdgeType, FailureKind, SafetyLevel, SemanticType


def test_model_enums_remain_string_compatible() -> None:
    assert str(FailureKind.MISSING_OUTPUT) == "missing_output"
    assert FailureKind.MISSING_OUTPUT == "missing_output"
    assert str(SafetyLevel.SAFE_READ) == "safe_read"
    assert EdgeType.CONTROL_FLOW == "control_flow"
    assert SemanticType.RETRIEVAL == "retrieval"
    assert Diagnosis.RETRIEVAL_GROUNDING_FAILURE == "retrieval_grounding_failure"
