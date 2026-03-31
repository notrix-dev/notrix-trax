"""OpenAI adapter tests."""

from __future__ import annotations

from pathlib import Path

from trax.adapters.openai import traced_chat
from trax.storage import get_run, list_steps_for_run
from trax.storage.artifacts import read_artifact


def test_traced_chat_auto_creates_run_and_step(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    response = traced_chat(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": "hello"}],
        call=lambda **_: {"id": "resp-1", "usage": {"total_tokens": 12}, "output_text": "hi"},
    )

    assert response["output_text"] == "hi"
    runs = list(__import__("trax.storage.repository", fromlist=["list_runs"]).list_runs())
    assert len(runs) == 1
    run = get_run(runs[0].id)
    assert run is not None
    steps = list_steps_for_run(run.id)
    assert len(steps) == 1
    assert steps[0].attributes["semantic_type"] == "llm"
    assert steps[0].attributes["model"] == "gpt-4.1-mini"
    assert read_artifact(steps[0].input_artifact_ref) == {"messages": [{"role": "user", "content": "hello"}]}
    assert read_artifact(steps[0].output_artifact_ref)["output_text"] == "hi"
