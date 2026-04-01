"""Evidence-based suggestion ranking helpers."""

from __future__ import annotations

from trax.explain.models import Diagnosis
from trax.models import Failure, SemanticType, Step


def rank_suggestions(
    diagnosis: Diagnosis,
    suggestions: tuple[str, ...],
    *,
    step: Step | None,
    failure: Failure,
) -> tuple[str, ...]:
    """Rank suggestions deterministically using available evidence."""
    scored: list[tuple[int, int, str]] = []
    top_k = None if step is None else step.attributes.get("top_k")
    semantic_type = _semantic_type_for_step(step)

    for index, suggestion in enumerate(suggestions):
        score = 0
        if diagnosis == Diagnosis.RETRIEVAL_GROUNDING_FAILURE:
            if suggestion == "increase top_k" and isinstance(top_k, int | float) and top_k <= 3:
                score += 20
            if suggestion == "add reranker" and semantic_type == SemanticType.RETRIEVAL:
                score += 10
        if diagnosis == Diagnosis.CONTROL_FLOW_LOOP:
            if suggestion == "add explicit retry limit":
                score += 20
        if diagnosis == Diagnosis.LATENCY_DEGRADATION:
            duration_ms = failure.evidence.get("duration_ms")
            if suggestion == "reduce slow step work or payload size" and isinstance(duration_ms, int | float):
                score += 10
        if diagnosis == Diagnosis.MISSING_EXECUTION_OUTPUT:
            if suggestion == "verify output artifact is written on every successful path":
                score += 15
        scored.append((-score, index, suggestion))

    scored.sort()
    return tuple(item[2] for item in scored)


def _semantic_type_for_step(step: Step | None) -> SemanticType | None:
    if step is None:
        return None
    value = step.attributes.get("semantic_type")
    if not isinstance(value, str) or not value:
        return None
    try:
        return SemanticType(value)
    except ValueError:
        return None
