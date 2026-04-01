"""Best-effort OTel trace import."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from trax.collector import InProcessCollector, make_event
from trax.models import EdgeType
from trax.models.core import utc_now
from trax.normalize import normalize_and_persist


def import_trace(trace: dict[str, Any] | str | Path) -> str:
    """Import a minimal OTel-like trace object or JSON file."""
    payload = _load_trace(trace)
    spans = payload.get("spans")
    if not isinstance(spans, list):
        raise ValueError("OTel trace must contain a spans list.")

    run_id = str(payload.get("trace_id") or payload.get("run_id") or f"otel-{utc_now()}")
    started_at = _first_timestamp(spans) or utc_now()
    collector = InProcessCollector()
    collector.collect(
        make_event(
            event_id=str(uuid.uuid4()),
            source_type="adapter",
            source_name="otel",
            event_kind="run_start",
            payload={
                "run_id": run_id,
                "name": str(payload.get("name") or "otel-import"),
                "started_at": started_at,
            },
        )
    )

    seen_span_ids: set[str] = set()
    for position, span in enumerate(spans, start=1):
        span_id = str(span.get("span_id") or span.get("id") or f"span-{position}")
        if span_id in seen_span_ids:
            span_id = f"{span_id}-{position}"
        seen_span_ids.add(span_id)
        attributes = dict(span.get("attributes") or {})
        collector.collect(
            make_event(
                event_id=str(uuid.uuid4()),
                source_type="adapter",
                source_name="otel",
                event_kind="step_end",
                payload={
                    "step_id": span_id,
                    "run_id": run_id,
                    "name": str(span.get("name") or f"span-{position}"),
                    "status": "completed",
                    "position": position,
                    "started_at": str(span.get("started_at") or started_at),
                    "ended_at": str(span.get("ended_at") or span.get("started_at") or started_at),
                    "parent_step_id": _parent_id(span, seen_span_ids),
                    "safety_level": attributes.get("safety_level"),
                    "attributes": attributes,
                },
            )
        )
        parent_id = span.get("parent_span_id")
        if parent_id is not None and str(parent_id) != span_id:
            collector.collect(
                make_event(
                    event_id=str(uuid.uuid4()),
                    source_type="adapter",
                    source_name="otel",
                    event_kind="edge",
                    payload={
                        "edge_id": f"{parent_id}->{span_id}",
                        "run_id": run_id,
                        "source_step_id": str(parent_id),
                        "target_step_id": span_id,
                        "edge_type": EdgeType.PARENT_CHILD,
                    },
                )
            )

    collector.collect(
        make_event(
            event_id=str(uuid.uuid4()),
            source_type="adapter",
            source_name="otel",
            event_kind="run_end",
            payload={
                "run_id": run_id,
                "status": "completed",
                "ended_at": _last_timestamp(spans) or started_at,
            },
        )
    )
    normalize_and_persist(collector.flush())
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
