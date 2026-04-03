"""Graph export tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from trax.sdk import end_run, start_run, trace_step


def test_graph_export_emits_linear_graph_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("graph-export-linear")
    trace_step("prepare", attributes={"semantic_type": "transform"})
    trace_step("answer", attributes={"semantic_type": "llm"})
    end_run(output_payload={"done": True})

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "graph", "--run-id", run.id, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["run"]["id"] == run.id
    assert [node["name"] for node in payload["nodes"]] == ["transform:prepare", "llm:answer"]
    assert payload["summary"] == {"edge_count": 1, "node_count": 2, "root_count": 1}


def test_graph_export_handles_scope_metadata_without_turning_it_into_structure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("graph-export-hybrid")
    parent = trace_step("parent", attributes={"semantic_type": "agent"})
    trace_step("child", parent_step_id=parent.id, attributes={"semantic_type": "retrieval"})
    end_run()

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "graph", "--run-id", run.id, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["nodes"][1]["scope_parent_step_id"] == parent.id
    assert all(edge["type"] != "parent_child" for edge in payload["edges"])


def test_graph_export_writes_json_to_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("graph-export-file")
    trace_step("fetch", attributes={"semantic_type": "retrieval"})
    end_run()
    output_path = tmp_path / "graph.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "trax.cli.main",
            "graph",
            "--run-id",
            run.id,
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["run"]["id"] == run.id


def test_graph_export_fails_for_missing_run_id(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "graph", "--run-id", "missing-run", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 1
    assert "Run not found: missing-run" in result.stderr


def test_graph_export_fails_for_unsupported_format(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "graph", "--run-id", "missing-run", "--format", "yaml"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 1
    assert "Unsupported graph export format: yaml" in result.stderr
