"""Simulation-only replay engine for persisted runs."""

from __future__ import annotations

from trax.graph import GraphValidationError, build_run_graph
from trax.replay.models import ReplayResult, ReplayStepResult
from trax.storage import get_run, list_edges_for_run, list_steps_for_run
from trax.storage.artifacts import read_artifact


class ReplayError(ValueError):
    """Raised when a run cannot be replayed safely."""


def replay_run(run_id: str) -> ReplayResult:
    """Replay a persisted run in simulation mode only."""
    run = get_run(run_id)
    if run is None:
        raise ReplayError(f"Run not found: {run_id}")

    try:
        graph = build_run_graph(
            run_id,
            list_steps_for_run(run_id),
            list_edges_for_run(run_id),
        )
    except GraphValidationError as exc:
        raise ReplayError(str(exc)) from exc

    step_results: list[ReplayStepResult] = []
    has_blocked = False

    for step in graph.topological_steps():
        safety_level = _safety_level_for_step(step.attributes)
        if safety_level in {"unsafe_write", "unknown"}:
            has_blocked = True
            step_results.append(
                ReplayStepResult(
                    step_id=step.id,
                    step_name=step.name,
                    position=step.position,
                    status="BLOCKED",
                    safety_level=safety_level,
                    source="safety-gate",
                    detail="replay blocked by v1 safety policy",
                )
            )
            continue

        if step.output_artifact_ref is None:
            raise ReplayError(
                f"Replay missing required output artifact for step {step.name} ({step.id})"
            )

        try:
            read_artifact(step.output_artifact_ref)
        except FileNotFoundError as exc:
            raise ReplayError(
                f"Replay missing required output artifact for step {step.name} ({step.id})"
            ) from exc

        step_results.append(
            ReplayStepResult(
                step_id=step.id,
                step_name=step.name,
                position=step.position,
                status="SIMULATED",
                safety_level=safety_level,
                source="stored-artifact",
                detail=step.output_artifact_ref,
            )
        )

    return ReplayResult(
        run_id=run_id,
        status="completed_with_blocks" if has_blocked else "completed",
        step_results=tuple(step_results),
    )


def _safety_level_for_step(attributes: dict[str, object]) -> str:
    raw_value = attributes.get("safety_level")
    if isinstance(raw_value, str) and raw_value:
        return raw_value
    return "unknown"
