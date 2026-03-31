"""CLI UX tests for Trax Feature 8."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from trax.sdk import end_run, start_run, trace_step


def test_list_shows_empty_state_when_no_runs_exist(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "list"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert "No runs found." in result.stdout


def test_list_shows_recent_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    first = start_run("first-run")
    end_run(output_payload={"ok": True})
    second = start_run("second-run")
    end_run(output_payload={"ok": True})

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "list"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert "Runs" in result.stdout
    assert second.id in result.stdout
    assert first.id in result.stdout
