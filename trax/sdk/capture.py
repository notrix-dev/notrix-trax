"""Minimal SDK primitives for local run capture."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Any

from trax.collector import InProcessCollector, make_event
from trax.models import Run, Step
from trax.models.core import utc_now
from trax.normalize import normalize_and_persist
from trax.storage import bootstrap_local_storage


@dataclass
class ActiveRun:
    id: str
    name: str
    step_count: int = 0
    last_step_id_by_parent: dict[str | None, str] | None = None


_STATE = threading.local()
_COLLECTOR = InProcessCollector()


def has_active_run() -> bool:
    """Return whether a run is currently active in this thread."""
    return getattr(_STATE, "active_run", None) is not None


def start_run(name: str, input_payload: Any = None, run_id: str | None = None) -> Run:
    """Start and persist a new run."""
    bootstrap_local_storage()
    resolved_run_id = run_id or str(uuid.uuid4())
    started_at = utc_now()
    _COLLECTOR.collect(
        make_event(
            event_id=str(uuid.uuid4()),
            source_type="sdk",
            source_name="capture",
            event_kind="run_start",
            payload={
                "run_id": resolved_run_id,
                "name": name,
                "input_payload": input_payload,
                "started_at": started_at,
            },
        )
    )
    normalize_and_persist(_COLLECTOR.flush())
    run = Run(
        id=resolved_run_id,
        name=name,
        status="running",
        started_at=started_at,
    )
    _STATE.active_run = ActiveRun(id=run.id, name=run.name, last_step_id_by_parent={None: ""})
    return run


def end_run(output_payload: Any = None, error_message: str | None = None) -> str:
    """Complete the active run if one exists."""
    active_run = getattr(_STATE, "active_run", None)
    if active_run is None:
        raise RuntimeError("No active run to end.")

    status = "failed" if error_message else "completed"
    _COLLECTOR.collect(
        make_event(
            event_id=str(uuid.uuid4()),
            source_type="sdk",
            source_name="capture",
            event_kind="run_end",
            payload={
                "run_id": active_run.id,
                "status": status,
                "ended_at": utc_now(),
                "output_payload": output_payload,
                "error_message": error_message,
            },
        )
    )
    normalize_and_persist(_COLLECTOR.flush())
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
    timestamp = utc_now()
    raw_attributes = attributes or {}
    safety_level = raw_attributes.get("safety_level")
    _COLLECTOR.collect(
        make_event(
            event_id=str(uuid.uuid4()),
            source_type="sdk",
            source_name="capture",
            event_kind="step_end",
            payload={
                "step_id": step_id,
                "run_id": active_run.id,
                "name": name,
                "status": "failed" if error_message else "completed",
                "position": active_run.step_count,
                "started_at": timestamp,
                "ended_at": timestamp,
                "safety_level": safety_level,
                "parent_step_id": parent_step_id,
                "input_payload": input_payload,
                "output_payload": output_payload,
                "attributes": raw_attributes,
                "error_message": error_message,
            },
        )
    )
    normalize_and_persist(_COLLECTOR.flush())

    if parent_step_id is not None:
        _COLLECTOR.collect(
            make_event(
                event_id=str(uuid.uuid4()),
                source_type="sdk",
                source_name="capture",
                event_kind="edge",
                payload={
                    "edge_id": str(uuid.uuid4()),
                    "run_id": active_run.id,
                    "source_step_id": parent_step_id,
                    "target_step_id": step_id,
                    "edge_type": "parent_child",
                },
            )
        )

    previous_step_id = active_run.last_step_id_by_parent.get(parent_step_id) if active_run.last_step_id_by_parent else None
    if previous_step_id:
        _COLLECTOR.collect(
            make_event(
                event_id=str(uuid.uuid4()),
                source_type="sdk",
                source_name="capture",
                event_kind="edge",
                payload={
                    "edge_id": str(uuid.uuid4()),
                    "run_id": active_run.id,
                    "source_step_id": previous_step_id,
                    "target_step_id": step_id,
                    "edge_type": "control_flow",
                },
            )
        )
    pending_edges = _COLLECTOR.flush()
    if pending_edges:
        normalize_and_persist(pending_edges)

    step = Step(
        id=step_id,
        run_id=active_run.id,
        name=name,
        status="failed" if error_message else "completed",
        position=active_run.step_count,
        started_at=timestamp,
        ended_at=timestamp,
        safety_level=safety_level if isinstance(safety_level, str) and safety_level else "unknown",
        parent_step_id=parent_step_id,
        attributes=raw_attributes,
        error_message=error_message,
    )
    assert active_run.last_step_id_by_parent is not None
    active_run.last_step_id_by_parent[parent_step_id] = step.id
    return step
