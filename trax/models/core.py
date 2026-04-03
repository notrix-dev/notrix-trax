"""Core capture models for the first usable Trax data path."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


class SafetyLevel(StrEnum):
    """Persisted step safety levels."""

    SAFE_READ = "safe_read"
    UNSAFE_WRITE = "unsafe_write"
    UNKNOWN = "unknown"


class EdgeType(StrEnum):
    """Persisted per-run graph edge kinds."""

    PARENT_CHILD = "parent_child"
    CONTROL_FLOW = "control_flow"


class FailureKind(StrEnum):
    """Persisted detector failure kinds."""

    MISSING_OUTPUT = "missing_output"
    EMPTY_RETRIEVAL = "empty_retrieval"
    LOOP_DETECTED = "loop_detected"
    LATENCY_ANOMALY = "latency_anomaly"


class SemanticType(StrEnum):
    """Common step semantic types stored in step attributes."""

    UNKNOWN = "unknown"
    TRANSFORM = "transform"
    RETRIEVAL = "retrieval"
    LLM = "llm"
    TOOL = "tool"
    AGENT = "agent"
    REASONING = "reasoning"
    IO = "io"
    RERANK = "rerank"


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
    safety_level: SafetyLevel = SafetyLevel.UNKNOWN
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
    edge_type: EdgeType


@dataclass(frozen=True)
class Failure:
    """Structured detector finding persisted for a run."""

    id: str
    run_id: str
    step_id: str | None
    kind: FailureKind
    severity: str
    confidence: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)
