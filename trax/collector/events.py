"""Collected event envelope for in-process ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trax.models.core import utc_now


@dataclass(frozen=True)
class CollectedEvent:
    event_id: str
    schema_version: str
    source_type: str
    source_name: str
    event_kind: str
    occurred_at: str
    payload: dict[str, Any] = field(default_factory=dict)


def make_event(
    *,
    event_id: str,
    source_type: str,
    source_name: str,
    event_kind: str,
    payload: dict[str, Any],
    occurred_at: str | None = None,
) -> CollectedEvent:
    return CollectedEvent(
        event_id=event_id,
        schema_version="1",
        source_type=source_type,
        source_name=source_name,
        event_kind=event_kind,
        occurred_at=occurred_at or utc_now(),
        payload=payload,
    )
