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
    assert "- [1] step-one (completed)" in result.stdout


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
