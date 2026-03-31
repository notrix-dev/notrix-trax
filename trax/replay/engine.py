"""Simulation-only replay engine for persisted runs."""

from __future__ import annotations

from trax.graph import GraphValidationError, build_run_graph
from trax.models import Step
from trax.replay.models import ReplayResult, ReplayStepResult, ReplayWindow
from trax.replay.safety import blocked_reason_for_step, safety_level_for_step
from trax.storage import get_run, list_edges_for_run, list_steps_for_run
from trax.storage.artifacts import read_artifact


class ReplayError(ValueError):
    """Raised when a run cannot be replayed safely."""


def replay_run(
    run_id: str,
    *,
    start_at: str | None = None,
    stop_at: str | None = None,
) -> ReplayResult:
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

    ordered_steps = graph.topological_steps()
    step_by_id = {step.id: step for step in ordered_steps}
    for step_id in filter(None, (start_at, stop_at)):
        if step_id not in step_by_id:
            raise ReplayError(f"Replay step not found in run {run_id}: {step_id}")

    start_index = 0 if start_at is None else _index_for_step_id(ordered_steps, start_at)
    stop_index = len(ordered_steps) - 1 if stop_at is None else _index_for_step_id(ordered_steps, stop_at)
    if start_index > stop_index:
        raise ReplayError("Replay window is invalid: start_at is after stop_at")

    effective_steps = ordered_steps[start_index : stop_index + 1]
    window = ReplayWindow(
        start_at=start_at,
        stop_at=stop_at,
        effective_step_ids=tuple(step.id for step in effective_steps),
    )

    _hydrate_pre_window_state(ordered_steps[:start_index])

    step_results: list[ReplayStepResult] = []
    effective_step_ids = set(window.effective_step_ids)
    for step in ordered_steps:
        safety_level = safety_level_for_step(step)
        if step.id not in effective_step_ids:
            step_results.append(
                ReplayStepResult(
                    step_id=step.id,
                    step_name=step.name,
                    position=step.position,
                    status="SKIPPED",
                    safety_level=safety_level,
                    source="window-filter",
                    detail="outside requested replay window",
                )
            )
            continue

        blocked_reason = blocked_reason_for_step(step)
        if blocked_reason is not None:
            step_results.append(
                ReplayStepResult(
                    step_id=step.id,
                    step_name=step.name,
                    position=step.position,
                    status="BLOCKED",
                    safety_level=safety_level,
                    source="safety-gate",
                    detail=blocked_reason,
                )
            )
            return ReplayResult(
                run_id=run_id,
                status="failed_safety_policy",
                window=window,
                step_results=tuple(step_results),
            )

        _require_step_artifact(step)
        step_results.append(
            ReplayStepResult(
                step_id=step.id,
                step_name=step.name,
                position=step.position,
                status="SIMULATED",
                safety_level=safety_level,
                source="stored-artifact",
                detail=step.output_artifact_ref or "-",
            )
        )

    return ReplayResult(
        run_id=run_id,
        status="completed",
        window=window,
        step_results=tuple(step_results),
    )


def _index_for_step_id(steps: list[Step], step_id: str) -> int:
    return next(index for index, step in enumerate(steps) if step.id == step_id)


def _hydrate_pre_window_state(steps: list[Step]) -> None:
    for step in steps:
        _require_step_artifact(step)


def _require_step_artifact(step: Step) -> None:
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
