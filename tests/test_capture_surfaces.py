"""Capture surface tests for FCV1.5-1."""

from __future__ import annotations

from pathlib import Path

import pytest

from trax import run, step, traced_step
from trax.sdk import end_run, start_run, trace_step
from trax.storage import get_run, list_steps_for_run
from trax.storage.artifacts import read_artifact


def test_ergonomic_run_and_step_capture_summary_payloads(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    with run("ergonomic-demo", input={"foo": "bar"}, capture_policy="summary") as current_run:
        with step(
            "prepare",
            input={"question": "Hello", "extra": "value"},
            attributes={"semantic_type": "transform", "safety_level": "safe_read"},
        ) as traced:
            traced.set_output({"normalized_question": "hello", "confidence": 1.0})

    persisted = get_run(current_run.id)
    steps = list_steps_for_run(current_run.id)

    assert persisted is not None
    assert len(steps) == 1
    assert steps[0].safety_level == "safe_read"
    assert read_artifact(steps[0].input_artifact_ref)["type"] == "dict"
    assert "preview" in read_artifact(steps[0].output_artifact_ref)


def test_ergonomic_step_output_assignment_persists_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    with run("assignment-demo") as current_run:
        with step(
            "retrieve_docs",
            input={"query": "hello"},
            attributes={"semantic_type": "retrieval", "safety_level": "safe_read"},
        ) as traced:
            traced.output = {"docs": [{"id": "doc-1", "text": "hello"}]}

    steps = list_steps_for_run(current_run.id)
    assert len(steps) == 1
    assert read_artifact(steps[0].output_artifact_ref)["preview"]["docs"][0]["id"] == "doc-1"


def test_traced_step_decorator_requires_active_run_and_records_step(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    @traced_step("normalize", attributes={"semantic_type": "transform", "safety_level": "safe_read"})
    def normalize(text: str) -> dict[str, str]:
        return {"normalized": text.lower()}

    with pytest.raises(RuntimeError, match="No active run"):
        normalize("Hello")

    with run("decorator-demo") as current_run:
        result = normalize("Hello")

    steps = list_steps_for_run(current_run.id)
    assert result["normalized"] == "hello"
    assert len(steps) == 1
    assert steps[0].name == "transform:normalize"


def test_low_level_api_remains_functional(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run_record = start_run("low-level", input_payload={"script": "demo"}, source_type="low_level")
    trace_step(
        "fetch",
        input_payload={"url": "https://example.test"},
        output_payload={"rows": 1},
        attributes={"semantic_type": "io", "safety_level": "safe_read"},
    )
    end_run(output_payload={"done": True})

    steps = list_steps_for_run(run_record.id)
    assert len(steps) == 1
    assert steps[0].safety_level == "safe_read"
