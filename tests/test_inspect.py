"""CLI inspect tests for Trax Feature 1."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from trax.sdk import end_run, start_run, trace_step


def test_inspect_prints_run_and_step_details(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("cli-demo", input_payload={"source": "script"})
    trace_step("step-one", input_payload={"a": 1}, output_payload={"b": 2})
    end_run(output_payload={"done": True})

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "inspect", run.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert f"Run: {run.id}" in result.stdout
    assert "Name: cli-demo" in result.stdout
    assert "- [1] unknown:step_one (completed)" in result.stdout
    assert "Graph:" in result.stdout
    assert "- [1] unknown:step_one (root)" in result.stdout


def test_inspect_renders_nested_graph(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("nested-demo")
    parent = trace_step("parent")
    trace_step("child-a", parent_step_id=parent.id)
    trace_step("child-b", parent_step_id=parent.id)
    end_run()

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "inspect", run.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert "Graph:" in result.stdout
    assert "- [1] unknown:parent (root)" in result.stdout
    assert "- [2] unknown:child_a (parent=" in result.stdout
    assert "Control Flow:" in result.stdout


def test_inspect_computes_duplicate_display_suffixes_without_persisting_them(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("duplicate-display-demo")
    parent = trace_step("prepare", attributes={"semantic_type": "transform"})
    trace_step("faq_search", parent_step_id=parent.id, attributes={"semantic_type": "retrieval"})
    trace_step("faq_search", parent_step_id=parent.id, attributes={"semantic_type": "retrieval"})
    end_run()

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "inspect", run.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert "retrieval:faq_search#1" in result.stdout
    assert "retrieval:faq_search#2" in result.stdout


def test_inspect_fails_for_invalid_run_id(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "inspect", "missing-run"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 1
    assert "Run not found: missing-run" in result.stderr


def test_inspect_filters_steps_and_handles_empty_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("filter-demo")
    trace_step("retrieval-step", attributes={"semantic_type": "retrieval"})
    trace_step("llm-step", attributes={"semantic_type": "llm"})
    end_run(output_payload={"done": True})

    filtered = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "inspect", run.id, "--step-type", "retrieval"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )
    empty = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "inspect", run.id, "--step-name", "missing-step"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert filtered.returncode == 0
    assert "retrieval-step" in filtered.stdout
    assert "llm-step" not in filtered.stdout
    assert empty.returncode == 0
    assert "No steps matched filter: step_name=missing-step" in empty.stdout
