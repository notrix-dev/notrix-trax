"""Minimal SDK primitives for local run capture."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from functools import wraps
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
    source_type: str = "low_level"
    capture_policy: str = "full_artifact"


_STATE = threading.local()
_COLLECTOR = InProcessCollector()


def has_active_run() -> bool:
    """Return whether a run is currently active in this thread."""
    return getattr(_STATE, "active_run", None) is not None


def start_run(
    name: str,
    input_payload: Any = None,
    run_id: str | None = None,
    *,
    source_type: str = "low_level",
    capture_policy: str = "full_artifact",
) -> Run:
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
                "input_payload": _apply_capture_policy(input_payload, capture_policy),
                "started_at": started_at,
                "source_type": source_type,
                "capture_policy": capture_policy,
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
    _STATE.active_run = ActiveRun(
        id=run.id,
        name=run.name,
        last_step_id_by_parent={None: ""},
        source_type=source_type,
        capture_policy=capture_policy,
    )
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
                "input_payload": _apply_capture_policy(input_payload, active_run.capture_policy),
                "output_payload": _apply_capture_policy(output_payload, active_run.capture_policy),
                "attributes": raw_attributes,
                "error_message": error_message,
                "source_type": active_run.source_type,
                "capture_policy": active_run.capture_policy,
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


class _RunScope:
    def __init__(self, name: str, input: Any = None, *, capture_policy: str = "summary") -> None:
        self._name = name
        self._input = input
        self._capture_policy = capture_policy
        self.run: Run | None = None
        self._created_run = False

    def __enter__(self) -> Run:
        if has_active_run():
            active_run = getattr(_STATE, "active_run", None)
            assert active_run is not None
            self.run = Run(id=active_run.id, name=active_run.name, status="running", started_at="")
            return self.run
        self.run = start_run(
            self._name,
            input_payload=self._input,
            source_type="ergonomic",
            capture_policy=self._capture_policy,
        )
        self._created_run = True
        return self.run

    def __exit__(self, exc_type: Any, exc: Any, _tb: Any) -> None:
        if not self._created_run:
            return
        end_run(error_message=str(exc) if exc is not None else None)


class _StepScope:
    def __init__(
        self,
        name: str,
        *,
        input: Any = None,
        output: Any = None,
        parent_step_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._input = input
        self._output = output
        self._parent_step_id = parent_step_id
        self._attributes = attributes

    @property
    def output(self) -> Any:
        return self._output

    @output.setter
    def output(self, value: Any) -> None:
        self._output = value

    def __enter__(self) -> "_StepScope":
        if not has_active_run():
            raise RuntimeError("No active run. Use trax.run(...) before trax.step(...).")
        return self

    def set_output(self, output: Any) -> None:
        self._output = output

    def __exit__(self, exc_type: Any, exc: Any, _tb: Any) -> None:
        trace_step(
            self._name,
            input_payload=self._input,
            output_payload=self._output,
            parent_step_id=self._parent_step_id,
            attributes=self._attributes,
            error_message=str(exc) if exc is not None else None,
        )


def run(name: str, input: Any = None, *, capture_policy: str = "summary") -> _RunScope:
    """Ergonomic run scope."""
    return _RunScope(name, input=input, capture_policy=capture_policy)


def step(
    name: str,
    *,
    input: Any = None,
    output: Any = None,
    parent_step_id: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> _StepScope:
    """Ergonomic step scope."""
    return _StepScope(
        name,
        input=input,
        output=output,
        parent_step_id=parent_step_id,
        attributes=attributes,
    )


def traced_step(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Any:
    """Decorator for lightweight step tracing."""

    def decorator(func: Any) -> Any:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not has_active_run():
                raise RuntimeError("No active run. Use trax.run(...) before @traced_step functions.")
            error_message: str | None = None
            result: Any = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as exc:
                error_message = str(exc)
                raise
            finally:
                trace_step(
                    name,
                    input_payload={"args": list(args), "kwargs": kwargs},
                    output_payload=result,
                    attributes=attributes,
                    error_message=error_message,
                )

        return wrapper

    return decorator


def _apply_capture_policy(payload: Any, capture_policy: str) -> Any:
    if capture_policy == "full_artifact":
        return payload
    if capture_policy == "metadata_only":
        return _payload_metadata(payload)
    return _payload_summary(payload)


def _payload_metadata(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, dict):
        return {"type": "dict", "keys": sorted(payload.keys())}
    if isinstance(payload, list):
        return {"type": "list", "len": len(payload)}
    return {"type": type(payload).__name__}


def _payload_summary(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, dict):
        summary: dict[str, Any] = {"type": "dict", "keys": sorted(payload.keys())}
        preview = {key: payload[key] for key in list(payload)[:3]}
        if preview:
            summary["preview"] = preview
        return summary
    if isinstance(payload, list):
        return {"type": "list", "len": len(payload), "preview": payload[:3]}
    return payload
