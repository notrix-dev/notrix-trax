"""Launch example smoke tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import re


def _run_example(script_path: str, trax_home: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["TRAX_HOME"] = str(trax_home)
    env["PYTHONPATH"] = "."
    return subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _run_cli(trax_home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["TRAX_HOME"] = str(trax_home)
    env["PYTHONPATH"] = "."
    return subprocess.run(
        [sys.executable, "-m", "trax.cli.main", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _extract_named_run_ids(output: str) -> dict[str, str]:
    return dict(re.findall(r"^\s*(baseline|changed|failed):\s+([a-f0-9-]+)$", output, flags=re.MULTILINE))


def test_basic_capture_example_runs(tmp_path: Path) -> None:
    result = _run_example("examples/basic_capture/app.py", tmp_path / "basic")

    assert result.returncode == 0
    assert result.stdout.strip()


def test_hero_diff_replay_example_creates_two_runs(tmp_path: Path) -> None:
    trax_home = tmp_path / "hero"
    result = _run_example("examples/hero_diff_replay.py", trax_home)

    assert result.returncode == 0
    run_ids = _extract_named_run_ids(result.stdout)
    assert "baseline" in run_ids
    assert "changed" in run_ids
    diff_result = _run_cli(trax_home, "diff", run_ids["baseline"], run_ids["changed"])
    assert diff_result.returncode == 0
    assert "transform:prepare_prompt" in diff_result.stdout
    assert "llm:generate_answer" in diff_result.stdout
    assert "key_config_changes" in diff_result.stdout


def test_rag_failure_example_creates_baseline_and_failed_runs(tmp_path: Path) -> None:
    trax_home = tmp_path / "rag"
    result = _run_example("examples/rag_failure/app.py", trax_home)

    assert result.returncode == 0
    run_ids = _extract_named_run_ids(result.stdout)
    assert "baseline" in run_ids
    assert "failed" in run_ids
    diff_result = _run_cli(trax_home, "diff", run_ids["baseline"], run_ids["failed"])
    assert diff_result.returncode == 0
    assert "retrieval:retrieve_docs" in diff_result.stdout
    assert "reasoning:explain_retrieval" in diff_result.stdout


def test_agent_loop_example_creates_structural_comparison_runs(tmp_path: Path) -> None:
    trax_home = tmp_path / "agent"
    result = _run_example("examples/agent_loop/app.py", trax_home)

    assert result.returncode == 0
    run_ids = _extract_named_run_ids(result.stdout)
    assert "baseline" in run_ids
    assert "changed" in run_ids
    diff_result = _run_cli(trax_home, "diff", run_ids["baseline"], run_ids["changed"])
    assert diff_result.returncode == 0
    assert "reasoning:repair_answer" in diff_result.stdout or "ADDED" in diff_result.stdout
