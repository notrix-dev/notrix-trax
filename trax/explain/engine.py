# Copyright 2026 Notrix LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Rule-based explanation engine."""

from __future__ import annotations

from trax.detect import DetectionError, analyze_run
from trax.explain.diagnosis import diagnosis_for_failure
from trax.explain.models import Diagnosis, Explanation, ExplanationResult
from trax.explain.playbooks import PLAYBOOKS
from trax.explain.ranker import rank_suggestions
from trax.models import Step
from trax.storage import get_run, list_failures_for_run, list_steps_for_run


class ExplainError(ValueError):
    """Raised when an explanation cannot be produced safely."""


def explain_run(run_id: str) -> ExplanationResult:
    """Generate deterministic explanations for a run."""
    run = get_run(run_id)
    if run is None:
        raise ExplainError(f"Run not found: {run_id}")

    failures = list_failures_for_run(run_id)
    if not failures:
        try:
            failures = analyze_run(run_id)
        except DetectionError as exc:
            raise ExplainError(str(exc)) from exc

    steps_by_id = {step.id: step for step in list_steps_for_run(run_id)}
    explanations: list[Explanation] = []

    for failure in failures:
        diagnosis, likely_causes = diagnosis_for_failure(failure)
        step = steps_by_id.get(failure.step_id) if failure.step_id else None
        suggestions = PLAYBOOKS.get(diagnosis, PLAYBOOKS[Diagnosis.UNKNOWN_FAILURE_PATTERN])
        ranked = rank_suggestions(diagnosis, suggestions, step=step, failure=failure)
        explanations.append(
            Explanation(
                run_id=run_id,
                failure_id=failure.id,
                diagnosis=diagnosis,
                step_id=failure.step_id,
                likely_causes=likely_causes,
                suggestions=ranked,
            )
        )

    return ExplanationResult(run_id=run_id, explanations=tuple(explanations))
