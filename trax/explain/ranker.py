"""Evidence-based suggestion ranking helpers."""

from __future__ import annotations

from trax.models import Failure, Step


def rank_suggestions(
    diagnosis: str,
    suggestions: tuple[str, ...],
    *,
    step: Step | None,
    failure: Failure,
) -> tuple[str, ...]:
    """Rank suggestions deterministically using available evidence."""
    scored: list[tuple[int, int, str]] = []
    top_k = None if step is None else step.attributes.get("top_k")
    semantic_type = None if step is None else step.attributes.get("semantic_type")

    for index, suggestion in enumerate(suggestions):
        score = 0
        if diagnosis == "retrieval_grounding_failure":
            if suggestion == "increase top_k" and isinstance(top_k, int | float) and top_k <= 3:
                score += 20
            if suggestion == "add reranker" and semantic_type == "retrieval":
                score += 10
        if diagnosis == "control_flow_loop":
            if suggestion == "add explicit retry limit":
                score += 20
        if diagnosis == "latency_degradation":
            duration_ms = failure.evidence.get("duration_ms")
            if suggestion == "reduce slow step work or payload size" and isinstance(duration_ms, int | float):
                score += 10
        if diagnosis == "missing_execution_output":
            if suggestion == "verify output artifact is written on every successful path":
                score += 15
        scored.append((-score, index, suggestion))

    scored.sort()
    return tuple(item[2] for item in scored)
