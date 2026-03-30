"""Detector engine tests for Trax Feature 5."""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from trax.detect import analyze_run
from trax.models import Edge, Run, Step
from trax.storage import bootstrap_local_storage, list_failures_for_run
from trax.storage.artifacts import write_artifact
from trax.storage.repository import insert_edge, insert_run, insert_step


def test_detect_healthy_run_has_no_failures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run = _persist_run(
        "healthy",
        run_started_at="2026-03-30T10:00:00+00:00",
        run_ended_at="2026-03-30T10:00:01+00:00",
        steps=[
            _step("prepare", 1, "2026-03-30T10:00:00+00:00", "2026-03-30T10:00:00.500000+00:00", {"semantic_type": "transform"}, {"ok": True}),
            _step("llm:answer", 2, "2026-03-30T10:00:00.500000+00:00", "2026-03-30T10:00:01+00:00", {"semantic_type": "llm"}, {"answer": "yes"}),
        ],
        edges=[("control_flow", 0, 1)],
        run_output_payload={"result": "ok"},
    )

    failures = analyze_run(run.id)

    assert failures == []


def test_detect_empty_retrieval_and_persists_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run = _persist_run(
        "empty-retrieval",
        run_started_at="2026-03-30T10:00:00+00:00",
        run_ended_at="2026-03-30T10:00:01+00:00",
        steps=[
            _step("retrieval:faq_search", 1, "2026-03-30T10:00:00+00:00", "2026-03-30T10:00:00.500000+00:00", {"semantic_type": "retrieval"}, {"docs": []}),
        ],
        edges=[],
    )

    failures = analyze_run(run.id)

    assert any(failure.kind == "empty_retrieval" for failure in failures)
    assert any(failure.kind == "empty_retrieval" for failure in list_failures_for_run(run.id))


def test_detect_loop_pattern(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run = _persist_run(
        "loop",
        run_started_at="2026-03-30T10:00:00+00:00",
        run_ended_at="2026-03-30T10:00:04+00:00",
        steps=[
            _step("retry_fetch", 1, "2026-03-30T10:00:00+00:00", "2026-03-30T10:00:01+00:00", {"semantic_type": "io"}, {"attempt": 1}),
            _step("retry_fetch", 2, "2026-03-30T10:00:01+00:00", "2026-03-30T10:00:02+00:00", {"semantic_type": "io"}, {"attempt": 2}),
            _step("retry_fetch", 3, "2026-03-30T10:00:02+00:00", "2026-03-30T10:00:03+00:00", {"semantic_type": "io"}, {"attempt": 3}),
        ],
        edges=[("control_flow", 0, 1), ("control_flow", 1, 2)],
    )

    failures = analyze_run(run.id)

    assert any(failure.kind == "loop_detected" for failure in failures)


def test_detect_missing_output_and_latency_anomaly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run = _persist_run(
        "missing-output-latency",
        run_started_at="2026-03-30T10:00:00+00:00",
        run_ended_at="2026-03-30T10:00:07+00:00",
        steps=[
            _step("slow-step", 1, "2026-03-30T10:00:00+00:00", "2026-03-30T10:00:03+00:00", {"semantic_type": "io"}, None),
        ],
        edges=[],
        run_output_payload=None,
    )

    failures = analyze_run(run.id)
    kinds = {failure.kind for failure in failures}

    assert "missing_output" in kinds
    assert "latency_anomaly" in kinds


def test_inspect_renders_failure_section(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run = _persist_run(
        "inspect-failures",
        run_started_at="2026-03-30T10:00:00+00:00",
        run_ended_at="2026-03-30T10:00:01+00:00",
        steps=[
            _step("retrieval:faq_search", 1, "2026-03-30T10:00:00+00:00", "2026-03-30T10:00:00.500000+00:00", {"semantic_type": "retrieval"}, {"docs": []}),
        ],
        edges=[],
    )

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "inspect", run.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert "Failures:" in result.stdout
    assert "empty_retrieval" in result.stdout


def _persist_run(
    name: str,
    *,
    run_started_at: str,
    run_ended_at: str,
    steps: list[dict[str, object]],
    edges: list[tuple[str, int, int]],
    run_output_payload: dict[str, object] | None = None,
) -> Run:
    bootstrap_local_storage()
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        name=name,
        status="completed",
        started_at=run_started_at,
        ended_at=run_ended_at,
        artifact_ref=write_artifact(run_id, "run-output", run_output_payload),
    )
    insert_run(run)

    persisted_steps: list[Step] = []
    for raw_step in steps:
        step = Step(
            id=str(uuid.uuid4()),
            run_id=run_id,
            name=str(raw_step["name"]),
            status="completed",
            position=int(raw_step["position"]),
            started_at=str(raw_step["started_at"]),
            ended_at=str(raw_step["ended_at"]),
            output_artifact_ref=write_artifact(run_id, f"step-{raw_step['position']}-output", raw_step["output_payload"]),
            attributes=dict(raw_step["attributes"]),
        )
        insert_step(step)
        persisted_steps.append(step)

    for edge_type, source_index, target_index in edges:
        insert_edge(
            Edge(
                id=str(uuid.uuid4()),
                run_id=run_id,
                source_step_id=persisted_steps[source_index].id,
                target_step_id=persisted_steps[target_index].id,
                edge_type=edge_type,
            )
        )
    return run


def _step(
    name: str,
    position: int,
    started_at: str,
    ended_at: str,
    attributes: dict[str, object],
    output_payload: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "name": name,
        "position": position,
        "started_at": started_at,
        "ended_at": ended_at,
        "attributes": attributes,
        "output_payload": output_payload,
    }
