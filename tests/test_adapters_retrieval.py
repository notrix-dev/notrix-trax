"""Retrieval adapter tests."""

from __future__ import annotations

from pathlib import Path

from trax.adapters.retrieval import traced_retrieval
from trax.storage import get_run, list_steps_for_run
from trax.storage.artifacts import read_artifact


def test_traced_retrieval_auto_creates_run_and_step(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    docs = traced_retrieval(
        query="hello",
        top_k=2,
        backend="simple_vector",
        retrieve=lambda **_: [{"id": "doc-1"}, {"id": "doc-2"}],
    )

    assert len(docs) == 2
    runs = list(__import__("trax.storage.repository", fromlist=["list_runs"]).list_runs())
    assert len(runs) == 1
    run = get_run(runs[0].id)
    assert run is not None
    steps = list_steps_for_run(run.id)
    assert len(steps) == 1
    assert steps[0].attributes["semantic_type"] == "retrieval"
    assert steps[0].attributes["top_k"] == 2
    assert read_artifact(steps[0].input_artifact_ref)["type"] == "dict"
    assert read_artifact(steps[0].output_artifact_ref)["type"] == "list"
