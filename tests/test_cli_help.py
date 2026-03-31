"""Smoke tests for the Trax CLI foundation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from trax.storage import bootstrap_local_storage

def test_cli_help_runs_successfully() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage: trax" in result.stdout
    assert "{import-otel,list,inspect,diff,replay,explain}" in result.stdout


def test_bootstrap_creates_local_storage_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    bootstrap = bootstrap_local_storage()

    assert bootstrap.app_dir.is_dir()
    assert bootstrap.artifacts_dir.is_dir()
    assert bootstrap.db_path.is_file()
