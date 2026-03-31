"""Minimal SDK primitives for local run capture."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Any

from trax.models import Edge, Run, Step
from trax.models.core import utc_now
from trax.storage import bootstrap_local_storage
from trax.storage.artifacts import write_artifact
from trax.storage.repository import insert_edge, insert_run, insert_step, update_run_completion


@dataclass
class ActiveRun:
    id: str
    name: str
    step_count: int = 0
    last_step_id_by_parent: dict[str | None, str] | None = None


_STATE = threading.local()


def has_active_run() -> bool:
    """Return whether a run is currently active in this thread."""
    return getattr(_STATE, "active_run", None) is not None


def start_run(name: str, input_payload: Any = None, run_id: str | None = None) -> Run:
    """Start and persist a new run."""
    bootstrap_local_storage()
    resolved_run_id = run_id or str(uuid.uuid4())
    artifact_ref = write_artifact(resolved_run_id, "run-input", input_payload)
    run = Run(
        id=resolved_run_id,
        name=name,
        status="running",
        started_at=utc_now(),
        artifact_ref=artifact_ref,
    )
    insert_run(run)
    _STATE.active_run = ActiveRun(id=run.id, name=run.name, last_step_id_by_parent={None: ""})
    return run


def end_run(output_payload: Any = None, error_message: str | None = None) -> str:
    """Complete the active run if one exists."""
    active_run = getattr(_STATE, "active_run", None)
    if active_run is None:
        raise RuntimeError("No active run to end.")

    artifact_ref = write_artifact(active_run.id, "run-output", output_payload)
    status = "failed" if error_message else "completed"
    update_run_completion(
        run_id=active_run.id,
        status=status,
        ended_at=utc_now(),
        artifact_ref=artifact_ref,
        error_message=error_message,
    )
    del _STATE.active_run
    return active_run.id


def trace_step(
    name: str,
    input_payload: Any = None,
    output_payload: Any = None,
    parent_step_id: str | None = None,
    attributes: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> Step:
    """Persist a step within the active run."""
    active_run = getattr(_STATE, "active_run", None)
    if active_run is None:
        raise RuntimeError("No active run. Call start_run() before trace_step().")

    bootstrap_local_storage()
    active_run.step_count += 1
    step_id = str(uuid.uuid4())
    input_artifact_ref = write_artifact(active_run.id, f"step-{active_run.step_count}-input", input_payload)
    output_artifact_ref = write_artifact(active_run.id, f"step-{active_run.step_count}-output", output_payload)
    timestamp = utc_now()
    step = Step(
        id=step_id,
        run_id=active_run.id,
        name=name,
        status="failed" if error_message else "completed",
        position=active_run.step_count,
        started_at=timestamp,
        ended_at=timestamp,
        parent_step_id=parent_step_id,
        input_artifact_ref=input_artifact_ref,
        output_artifact_ref=output_artifact_ref,
        attributes=attributes or {},
        error_message=error_message,
    )
    insert_step(step)
    if parent_step_id is not None:
        insert_edge(
            Edge(
                id=str(uuid.uuid4()),
                run_id=active_run.id,
                source_step_id=parent_step_id,
                target_step_id=step.id,
                edge_type="parent_child",
            )
        )

    sibling_key = parent_step_id
    previous_step_id = (active_run.last_step_id_by_parent or {}).get(sibling_key)
    if previous_step_id:
        insert_edge(
            Edge(
                id=str(uuid.uuid4()),
                run_id=active_run.id,
                source_step_id=previous_step_id,
                target_step_id=step.id,
                edge_type="control_flow",
            )
        )

    assert active_run.last_step_id_by_parent is not None
    active_run.last_step_id_by_parent[sibling_key] = step.id
    return step
