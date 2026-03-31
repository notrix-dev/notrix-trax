"""OTel adapter tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from trax.adapters.otel import import_trace
from trax.storage import get_run, list_steps_for_run


def test_import_trace_maps_basic_spans_to_steps(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run_id = import_trace(
        {
            "trace_id": "trace-1",
            "spans": [
                {"span_id": "s1", "name": "root", "started_at": "2026-03-30T10:00:00+00:00", "ended_at": "2026-03-30T10:00:01+00:00", "attributes": {"semantic_type": "llm"}},
                {"span_id": "s2", "parent_span_id": "s1", "name": "child", "started_at": "2026-03-30T10:00:01+00:00", "ended_at": "2026-03-30T10:00:02+00:00", "attributes": {"semantic_type": "retrieval"}},
            ],
        }
    )

    run = get_run(run_id)
    assert run is not None
    steps = list_steps_for_run(run_id)
    assert [step.id for step in steps] == ["s1", "s2"]
    assert steps[1].parent_step_id == "s1"


def test_import_otel_cli_imports_trace_file(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "trace_id": "trace-cli",
                "spans": [
                    {"span_id": "s1", "name": "root", "started_at": "2026-03-30T10:00:00+00:00", "ended_at": "2026-03-30T10:00:01+00:00"}
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "import-otel", str(trace_path)],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert "OTel Import:" in result.stdout
