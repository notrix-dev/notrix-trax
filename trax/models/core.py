"""Core capture models for the first usable Trax data path."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Run:
    """Captured run metadata."""

    id: str
    name: str
    status: str
    started_at: str
    ended_at: str | None = None
    artifact_ref: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class Step:
    """Captured step metadata within a run."""

    id: str
    run_id: str
    name: str
    status: str
    position: int
    started_at: str
    ended_at: str
    parent_step_id: str | None = None
    input_artifact_ref: str | None = None
    output_artifact_ref: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass(frozen=True)
class Edge:
    """Directed relationship between two steps in the same run."""

    id: str
    run_id: str
    source_step_id: str
    target_step_id: str
    edge_type: str


@dataclass(frozen=True)
class Failure:
    """Structured detector finding persisted for a run."""

    id: str
    run_id: str
    step_id: str | None
    kind: str
    severity: str
    confidence: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Explanation:
    """Structured explanation produced from failures and run evidence."""

    run_id: str
    failure_id: str
    diagnosis: str
    step_id: str | None
    likely_causes: tuple[str, ...]
    suggestions: tuple[str, ...]
