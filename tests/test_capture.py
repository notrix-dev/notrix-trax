"""Capture and storage tests for Trax Feature 1."""

from __future__ import annotations

from pathlib import Path

from trax.sdk import end_run, start_run, trace_step
from trax.storage import get_run, list_steps_for_run
from trax.storage.artifacts import read_artifact


def test_run_and_step_persist_with_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("demo-script", input_payload={"script": "demo"})
    trace_step(
        "fetch-data",
        input_payload={"url": "https://example.test"},
        output_payload={"rows": 3},
        attributes={"semantic_type": "io"},
    )
    end_run(output_payload={"result": "ok"})

    persisted_run = get_run(run.id)
    assert persisted_run is not None
    assert persisted_run.name == "demo-script"
    assert persisted_run.status == "completed"
    assert read_artifact(persisted_run.artifact_ref) == {"result": "ok"}

    steps = list_steps_for_run(run.id)
    assert len(steps) == 1
    assert steps[0].run_id == run.id
    assert steps[0].position == 1
    assert read_artifact(steps[0].input_artifact_ref) == {"url": "https://example.test"}
    assert read_artifact(steps[0].output_artifact_ref) == {"rows": 3}


def test_run_can_complete_without_steps(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("empty-run")
    end_run()

    persisted_run = get_run(run.id)
    assert persisted_run is not None
    assert persisted_run.status == "completed"
    assert list_steps_for_run(run.id) == []
