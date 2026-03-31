"""Replay engine tests for Trax Feature 4."""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from trax.models import Edge, Run, Step
from trax.replay import ReplayError, replay_run
from trax.storage import bootstrap_local_storage
from trax.storage.artifacts import write_artifact
from trax.storage.repository import insert_edge, insert_run, insert_step, list_steps_for_run


def test_replay_simulates_safe_steps_in_deterministic_order(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-safe",
        steps=[
            _step("prepare", 1, safety_level="safe_read", output_payload={"ok": 1}),
            _step("llm:answer", 2, safety_level="safe_read", output_payload={"answer": "yes"}),
        ],
        edges=[("control_flow", 0, 1)],
    )

    result = replay_run(run.id)

    assert result.status == "completed"
    assert result.window.effective_step_ids
    assert [step.status for step in result.step_results] == ["SIMULATED", "SIMULATED"]
    assert [step.step_name for step in result.step_results] == ["prepare", "llm:answer"]


def test_replay_blocks_unsafe_write_step(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-unsafe",
        steps=[_step("db:update", 1, safety_level="unsafe_write", output_payload={"updated": True})],
        edges=[],
    )

    result = replay_run(run.id)

    assert result.status == "failed_safety_policy"
    assert result.blocked_count == 1
    assert result.step_results[0].safety_level == "unsafe_write"


def test_replay_blocks_unknown_safety_level(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-unknown",
        steps=[_step("tool:call", 1, safety_level=None, output_payload={"ok": True})],
        edges=[],
    )

    result = replay_run(run.id)

    assert result.status == "failed_safety_policy"
    assert result.step_results[0].safety_level == "unknown"


def test_replay_fails_when_required_artifact_is_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-missing-artifact",
        steps=[_step("fetch", 1, safety_level="safe_read", output_payload={"ok": True})],
        edges=[],
    )
    artifact_path = tmp_path / ".trax" / "artifacts" / run.id / "step-1-output.json"
    artifact_path.unlink()

    with pytest.raises(ReplayError, match="missing required output artifact"):
        replay_run(run.id)


def test_replay_cli_renders_simulated_and_blocked_steps(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-cli",
        steps=[
            _step("prepare", 1, safety_level="safe_read", output_payload={"ok": 1}),
            _step("db:update", 2, safety_level="unsafe_write", output_payload={"updated": True}),
        ],
        edges=[("control_flow", 0, 1)],
    )

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "replay", run.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 1
    assert "Replay:" in result.stdout
    assert "[SIMULATED] prepare" in result.stdout
    assert "[BLOCKED] db:update" in result.stdout


def test_replay_start_only_window_skips_prior_steps(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-start-only",
        steps=[
            _step("one", 1, safety_level="safe_read", output_payload={"ok": 1}),
            _step("two", 2, safety_level="safe_read", output_payload={"ok": 2}),
            _step("three", 3, safety_level="safe_read", output_payload={"ok": 3}),
        ],
        edges=[("control_flow", 0, 1), ("control_flow", 1, 2)],
    )
    step_ids = _list_step_ids(run.id)

    result = replay_run(run.id, start_at=step_ids[1])

    assert result.window.start_at == step_ids[1]
    assert [step.status for step in result.step_results] == ["SKIPPED", "SIMULATED", "SIMULATED"]


def test_replay_stop_only_window_skips_later_steps(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-stop-only",
        steps=[
            _step("one", 1, safety_level="safe_read", output_payload={"ok": 1}),
            _step("two", 2, safety_level="safe_read", output_payload={"ok": 2}),
            _step("three", 3, safety_level="safe_read", output_payload={"ok": 3}),
        ],
        edges=[("control_flow", 0, 1), ("control_flow", 1, 2)],
    )
    step_ids = _list_step_ids(run.id)

    result = replay_run(run.id, stop_at=step_ids[1])

    assert result.window.stop_at == step_ids[1]
    assert [step.status for step in result.step_results] == ["SIMULATED", "SIMULATED", "SKIPPED"]


def test_replay_bounded_and_single_step_windows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-bounded",
        steps=[
            _step("one", 1, safety_level="safe_read", output_payload={"ok": 1}),
            _step("two", 2, safety_level="safe_read", output_payload={"ok": 2}),
            _step("three", 3, safety_level="safe_read", output_payload={"ok": 3}),
        ],
        edges=[("control_flow", 0, 1), ("control_flow", 1, 2)],
    )
    step_ids = _list_step_ids(run.id)

    bounded = replay_run(run.id, start_at=step_ids[1], stop_at=step_ids[2])
    single = replay_run(run.id, start_at=step_ids[1], stop_at=step_ids[1])

    assert [step.status for step in bounded.step_results] == ["SKIPPED", "SIMULATED", "SIMULATED"]
    assert [step.status for step in single.step_results] == ["SKIPPED", "SIMULATED", "SKIPPED"]


def test_replay_invalid_step_and_reversed_window_fail_clearly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-invalid-window",
        steps=[
            _step("one", 1, safety_level="safe_read", output_payload={"ok": 1}),
            _step("two", 2, safety_level="safe_read", output_payload={"ok": 2}),
        ],
        edges=[("control_flow", 0, 1)],
    )
    step_ids = _list_step_ids(run.id)

    with pytest.raises(ReplayError, match="Replay step not found"):
        replay_run(run.id, start_at="missing-step")

    with pytest.raises(ReplayError, match="start_at is after stop_at"):
        replay_run(run.id, start_at=step_ids[1], stop_at=step_ids[0])


def test_replay_partial_window_requires_upstream_artifacts_for_hydration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = _persist_run(
        "replay-hydration",
        steps=[
            _step("one", 1, safety_level="safe_read", output_payload={"ok": 1}),
            _step("two", 2, safety_level="safe_read", output_payload={"ok": 2}),
        ],
        edges=[("control_flow", 0, 1)],
    )
    step_ids = _list_step_ids(run.id)
    artifact_path = tmp_path / ".trax" / "artifacts" / run.id / "step-1-output.json"
    artifact_path.unlink()

    with pytest.raises(ReplayError, match="missing required output artifact"):
        replay_run(run.id, start_at=step_ids[1])


def _persist_run(name: str, *, steps: list[dict[str, object]], edges: list[tuple[str, int, int]]) -> Run:
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
    return run


def _step(name: str, position: int, *, safety_level: str | None, output_payload: dict[str, object]) -> dict[str, object]:
    attributes: dict[str, object] = {}
    if safety_level is not None:
        attributes["safety_level"] = safety_level
    return {
        "name": name,
        "position": position,
        "attributes": attributes,
        "output_payload": output_payload,
    }


def _list_step_ids(run_id: str) -> list[str]:
    return [step.id for step in list_steps_for_run(run_id)]
