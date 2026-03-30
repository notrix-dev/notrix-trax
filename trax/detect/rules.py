"""Deterministic single-run detector rules."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from trax.graph import RunGraph
from trax.models import Failure, Run, Step
from trax.storage.artifacts import read_artifact


def detect_failures(run: Run, graph: RunGraph) -> list[Failure]:
    failures: list[Failure] = []
    failures.extend(_detect_missing_output(run, graph))
    failures.extend(_detect_empty_retrieval(run, graph))
    failures.extend(_detect_loop(graph))
    failures.extend(_detect_latency_anomaly(run, graph))
    return failures


def _detect_missing_output(run: Run, graph: RunGraph) -> list[Failure]:
    failures: list[Failure] = []
    if run.artifact_ref is None:
        failures.append(
            _failure(
                run_id=run.id,
                step_id=None,
                kind="missing_output",
                severity="high",
                confidence="high",
                summary="Run is missing an output artifact reference.",
                evidence={"target": "run"},
            )
        )

    for step in graph.topological_steps():
        if step.output_artifact_ref is None:
            failures.append(
                _failure(
                    run_id=run.id,
                    step_id=step.id,
                    kind="missing_output",
                    severity="high",
                    confidence="high",
                    summary=f"Step {step.name} is missing an output artifact reference.",
                    evidence={"step_name": step.name, "position": step.position},
                )
            )
            continue

        try:
            read_artifact(step.output_artifact_ref)
        except FileNotFoundError:
            failures.append(
                _failure(
                    run_id=run.id,
                    step_id=step.id,
                    kind="missing_output",
                    severity="high",
                    confidence="high",
                    summary=f"Step {step.name} output artifact is missing from storage.",
                    evidence={"step_name": step.name, "artifact_ref": step.output_artifact_ref},
                )
            )
    return failures


def _detect_empty_retrieval(run: Run, graph: RunGraph) -> list[Failure]:
    failures: list[Failure] = []
    for step in graph.topological_steps():
        semantic_type = step.attributes.get("semantic_type")
        name = step.name.lower()
        if semantic_type != "retrieval" and "retriev" not in name and "search" not in name:
            continue
        if step.output_artifact_ref is None:
            continue
        try:
            payload = read_artifact(step.output_artifact_ref)
        except FileNotFoundError:
            continue
        docs = _retrieved_docs(payload)
        if docs == []:
            failures.append(
                _failure(
                    run_id=run.id,
                    step_id=step.id,
                    kind="empty_retrieval",
                    severity="medium",
                    confidence="high",
                    summary=f"Retrieval step {step.name} returned no documents.",
                    evidence={"step_name": step.name, "position": step.position},
                )
            )
    return failures


def _detect_loop(graph: RunGraph) -> list[Failure]:
    repeated: dict[tuple[str, str | None], list[Step]] = {}
    for step in graph.topological_steps():
        key = (step.name, step.parent_step_id)
        repeated.setdefault(key, []).append(step)

    failures: list[Failure] = []
    for (step_name, _parent_id), steps in repeated.items():
        if len(steps) >= 3:
            failures.append(
                _failure(
                    run_id=steps[0].run_id,
                    step_id=steps[-1].id,
                    kind="loop_detected",
                    severity="medium",
                    confidence="medium",
                    summary=f"Repeated step pattern detected for {step_name}.",
                    evidence={"step_name": step_name, "count": len(steps)},
                )
            )
    return failures


def _detect_latency_anomaly(run: Run, graph: RunGraph) -> list[Failure]:
    failures: list[Failure] = []
    duration_ms = _duration_ms(run.started_at, run.ended_at)
    if duration_ms is not None and duration_ms >= 5_000:
        failures.append(
            _failure(
                run_id=run.id,
                step_id=None,
                kind="latency_anomaly",
                severity="medium",
                confidence="medium",
                summary="Run latency exceeded the v1 local anomaly threshold.",
                evidence={"duration_ms": duration_ms, "threshold_ms": 5000},
            )
        )

    for step in graph.topological_steps():
        step_duration_ms = _duration_ms(step.started_at, step.ended_at)
        if step_duration_ms is not None and step_duration_ms >= 2_000:
            failures.append(
                _failure(
                    run_id=run.id,
                    step_id=step.id,
                    kind="latency_anomaly",
                    severity="low",
                    confidence="medium",
                    summary=f"Step {step.name} exceeded the v1 step latency threshold.",
                    evidence={"step_name": step.name, "duration_ms": step_duration_ms, "threshold_ms": 2000},
                )
            )
    return failures


def _retrieved_docs(payload: Any) -> list[Any] | None:
    if isinstance(payload, dict):
        for key in ("docs", "documents", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    if isinstance(payload, list):
        return payload
    return None


def _duration_ms(started_at: str, ended_at: str | None) -> int | None:
    if ended_at is None:
        return None
    started = datetime.fromisoformat(started_at)
    ended = datetime.fromisoformat(ended_at)
    return int((ended - started).total_seconds() * 1000)


def _failure(
    *,
    run_id: str,
    step_id: str | None,
    kind: str,
    severity: str,
    confidence: str,
    summary: str,
    evidence: dict[str, Any],
) -> Failure:
    return Failure(
        id=str(uuid.uuid4()),
        run_id=run_id,
        step_id=step_id,
        kind=kind,
        severity=severity,
        confidence=confidence,
        summary=summary,
        evidence=evidence,
    )
