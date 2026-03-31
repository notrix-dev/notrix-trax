"""Normalization from collected events into canonical persistence."""

from __future__ import annotations

import uuid
from typing import Any

from trax.collector import CollectedEvent
from trax.models import Edge, Run, Step
from trax.storage import bootstrap_local_storage
from trax.storage.artifacts import write_artifact
from trax.storage.repository import insert_edge, insert_run, insert_step, update_run_completion


def normalize_and_persist(events: list[CollectedEvent]) -> dict[str, Any]:
    """Normalize a collected event batch and persist canonical records."""
    bootstrap_local_storage()
    state: dict[str, Any] = {}
    for event in events:
        payload = event.payload
        if event.event_kind == "run_start":
            artifact_ref = write_artifact(payload["run_id"], "run-input", payload.get("input_payload"))
            run = Run(
                id=payload["run_id"],
                name=payload["name"],
                status="running",
                started_at=payload["started_at"],
                artifact_ref=artifact_ref,
            )
            insert_run(run)
            state[payload["run_id"]] = {}
        elif event.event_kind == "run_end":
            artifact_ref = write_artifact(payload["run_id"], "run-output", payload.get("output_payload"))
            update_run_completion(
                run_id=payload["run_id"],
                status=payload["status"],
                ended_at=payload["ended_at"],
                artifact_ref=artifact_ref,
                error_message=payload.get("error_message"),
            )
        elif event.event_kind == "step_end":
            input_ref = write_artifact(payload["run_id"], f"step-{payload['position']}-input", payload.get("input_payload"))
            output_ref = write_artifact(payload["run_id"], f"step-{payload['position']}-output", payload.get("output_payload"))
            step = Step(
                id=payload["step_id"],
                run_id=payload["run_id"],
                name=payload["name"],
                status=payload["status"],
                position=payload["position"],
                started_at=payload["started_at"],
                ended_at=payload["ended_at"],
                safety_level=payload.get("safety_level") or "unknown",
                parent_step_id=payload.get("parent_step_id"),
                input_artifact_ref=input_ref,
                output_artifact_ref=output_ref,
                attributes=dict(payload.get("attributes") or {}),
                error_message=payload.get("error_message"),
            )
            insert_step(step)
        elif event.event_kind == "edge":
            insert_edge(
                Edge(
                    id=payload["edge_id"],
                    run_id=payload["run_id"],
                    source_step_id=payload["source_step_id"],
                    target_step_id=payload["target_step_id"],
                    edge_type=payload["edge_type"],
                )
            )
    return state
