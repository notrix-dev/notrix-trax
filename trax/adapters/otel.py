"""Best-effort OTel trace import."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trax.models import Edge, Run, Step
from trax.models.core import utc_now
from trax.storage import bootstrap_local_storage
from trax.storage.repository import insert_edge, insert_run, insert_step, update_run_completion


def import_trace(trace: dict[str, Any] | str | Path) -> str:
    """Import a minimal OTel-like trace object or JSON file."""
    payload = _load_trace(trace)
    spans = payload.get("spans")
    if not isinstance(spans, list):
        raise ValueError("OTel trace must contain a spans list.")

    bootstrap_local_storage()
    run_id = str(payload.get("trace_id") or payload.get("run_id") or f"otel-{utc_now()}")
    started_at = _first_timestamp(spans) or utc_now()
    run = Run(
        id=run_id,
        name=str(payload.get("name") or "otel-import"),
        status="running",
        started_at=started_at,
    )
    insert_run(run)

    seen_span_ids: set[str] = set()
    for position, span in enumerate(spans, start=1):
        span_id = str(span.get("span_id") or span.get("id") or f"span-{position}")
        if span_id in seen_span_ids:
            span_id = f"{span_id}-{position}"
        seen_span_ids.add(span_id)
        attributes = dict(span.get("attributes") or {})
        step = Step(
            id=span_id,
            run_id=run_id,
            name=str(span.get("name") or f"span-{position}"),
            status="completed",
            position=position,
            started_at=str(span.get("started_at") or started_at),
            ended_at=str(span.get("ended_at") or span.get("started_at") or started_at),
            parent_step_id=_parent_id(span, seen_span_ids),
            attributes=attributes,
        )
        insert_step(step)

    for span in spans:
        span_id = str(span.get("span_id") or span.get("id") or "")
        parent_id = span.get("parent_span_id")
        if not span_id or not parent_id:
            continue
        normalized_parent_id = str(parent_id)
        normalized_span_id = str(span_id)
        if normalized_parent_id == normalized_span_id:
            continue
        insert_edge(
            Edge(
                id=f"{normalized_parent_id}->{normalized_span_id}",
                run_id=run_id,
                source_step_id=normalized_parent_id,
                target_step_id=normalized_span_id,
                edge_type="parent_child",
            )
        )

    update_run_completion(run_id=run_id, status="completed", ended_at=_last_timestamp(spans) or started_at)
    return run_id


def _load_trace(trace: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(trace, dict):
        return trace
    path = Path(trace)
    return json.loads(path.read_text(encoding="utf-8"))


def _first_timestamp(spans: list[dict[str, Any]]) -> str | None:
    values = [str(span["started_at"]) for span in spans if span.get("started_at")]
    return min(values) if values else None


def _last_timestamp(spans: list[dict[str, Any]]) -> str | None:
    values = [str(span.get("ended_at") or span.get("started_at")) for span in spans if span.get("started_at")]
    return max(values) if values else None


def _parent_id(span: dict[str, Any], seen_span_ids: set[str]) -> str | None:
    parent_id = span.get("parent_span_id")
    if parent_id is None:
        return None
    resolved = str(parent_id)
    return resolved if resolved in seen_span_ids else None
