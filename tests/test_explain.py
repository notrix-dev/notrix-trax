"""Explanation engine tests for Trax Feature 6."""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from trax.explain import explain_run
from trax.models import Edge, Failure, Run, Step
from trax.storage import bootstrap_local_storage
from trax.storage.artifacts import write_artifact
from trax.storage.repository import insert_edge, insert_run, insert_step, replace_failures_for_run


def test_explain_single_failure_maps_to_diagnosis_and_ranked_suggestions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run, steps = _persist_run(
        "explain-retrieval",
        steps=[
            _step(
                "retrieval:faq_search",
                1,
                {"semantic_type": "retrieval", "top_k": 1},
                {"docs": []},
            ),
        ],
        edges=[],
    )
    replace_failures_for_run(
        run.id,
        [
            Failure(
                id=str(uuid.uuid4()),
                run_id=run.id,
                step_id=steps[0].id,
                kind="empty_retrieval",
                severity="medium",
                confidence="high",
                summary="Retrieval returned no docs.",
                evidence={"step_name": steps[0].name},
            )
        ],
    )

    result = explain_run(run.id)

    assert len(result.explanations) == 1
    explanation = result.explanations[0]
    assert explanation.diagnosis == "retrieval_grounding_failure"
    assert explanation.suggestions[0] == "increase top_k"


def test_explain_multiple_failures_create_multiple_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run, steps = _persist_run(
        "explain-multi",
        steps=[
            _step("retry_fetch", 1, {"semantic_type": "io"}, {"attempt": 1}),
            _step("retry_fetch", 2, {"semantic_type": "io"}, {"attempt": 2}),
        ],
        edges=[("control_flow", 0, 1)],
    )
    replace_failures_for_run(
        run.id,
        [
            Failure(
                id=str(uuid.uuid4()),
                run_id=run.id,
                step_id=steps[0].id,
                kind="latency_anomaly",
                severity="low",
                confidence="medium",
                summary="Slow step.",
                evidence={"duration_ms": 3000},
            ),
            Failure(
                id=str(uuid.uuid4()),
                run_id=run.id,
                step_id=steps[1].id,
                kind="loop_detected",
                severity="medium",
                confidence="medium",
                summary="Loop pattern.",
                evidence={"count": 3},
            ),
        ],
    )

    result = explain_run(run.id)

    assert len(result.explanations) == 2
    assert {item.diagnosis for item in result.explanations} == {"latency_degradation", "control_flow_loop"}


def test_explain_no_failures_returns_empty_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run, _steps = _persist_run(
        "explain-none",
        steps=[_step("prepare", 1, {"semantic_type": "transform"}, {"ok": True})],
        edges=[],
    )

    result = explain_run(run.id)

    assert result.explanations == ()


def test_explain_cli_renders_actionable_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run, steps = _persist_run(
        "explain-cli",
        steps=[
            _step(
                "retrieval:faq_search",
                1,
                {"semantic_type": "retrieval", "top_k": 1},
                {"docs": []},
            ),
        ],
        edges=[],
    )
    replace_failures_for_run(
        run.id,
        [
            Failure(
                id=str(uuid.uuid4()),
                run_id=run.id,
                step_id=steps[0].id,
                kind="empty_retrieval",
                severity="medium",
                confidence="high",
                summary="Retrieval returned no docs.",
                evidence={"step_name": steps[0].name},
            )
        ],
    )

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "explain", run.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert f"Run: {run.id}" in result.stdout
    assert "Failure: retrieval_grounding_failure" in result.stdout
    assert "Suggestions:" in result.stdout
    assert "- increase top_k" in result.stdout


def test_explain_filters_failures_and_handles_empty_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run, steps = _persist_run(
        "explain-filter",
        steps=[
            _step("retrieval:faq_search", 1, {"semantic_type": "retrieval", "top_k": 1}, {"docs": []}),
        ],
        edges=[],
    )
    replace_failures_for_run(
        run.id,
        [
            Failure(
                id=str(uuid.uuid4()),
                run_id=run.id,
                step_id=steps[0].id,
                kind="empty_retrieval",
                severity="medium",
                confidence="high",
                summary="Retrieval returned no docs.",
                evidence={"step_name": steps[0].name},
            )
        ],
    )

    filtered = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "explain", run.id, "--failure-kind", "empty_retrieval"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )
    empty = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "explain", run.id, "--severity", "high"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert filtered.returncode == 0
    assert "retrieval_grounding_failure" in filtered.stdout
    assert empty.returncode == 0
    assert "No failures matched filter: severity=high" in empty.stdout


def _persist_run(name: str, *, steps: list[dict[str, object]], edges: list[tuple[str, int, int]]) -> tuple[Run, list[Step]]:
    bootstrap_local_storage()
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        name=name,
        status="completed",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:01+00:00",
        artifact_ref=write_artifact(run_id, "run-output", {"result": "ok"}),
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
            started_at="2026-03-30T10:00:00+00:00",
            ended_at="2026-03-30T10:00:01+00:00",
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
    return run, persisted_steps


def _step(name: str, position: int, attributes: dict[str, object], output_payload: dict[str, object]) -> dict[str, object]:
    return {
        "name": name,
        "position": position,
        "attributes": attributes,
        "output_payload": output_payload,
    }
