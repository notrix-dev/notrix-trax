"""Normalizer tests for canonical persistence."""

from __future__ import annotations

import uuid
from pathlib import Path

from trax.collector import make_event
from trax.normalize import normalize_and_persist
from trax.storage import get_run, list_edges_for_run, list_steps_for_run


def test_normalizer_persists_canonical_run_step_and_edge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run_id = str(uuid.uuid4())
    step_id = str(uuid.uuid4())

    normalize_and_persist(
        [
            make_event(
                event_id=str(uuid.uuid4()),
                source_type="sdk",
                source_name="test",
                event_kind="run_start",
                payload={"run_id": run_id, "name": "demo", "started_at": "2026-03-31T00:00:00+00:00"},
            ),
            make_event(
                event_id=str(uuid.uuid4()),
                source_type="sdk",
                source_name="test",
                event_kind="step_end",
                payload={
                    "step_id": step_id,
                    "run_id": run_id,
                    "name": "fetch",
                    "status": "completed",
                    "position": 1,
                    "started_at": "2026-03-31T00:00:00+00:00",
                    "ended_at": "2026-03-31T00:00:01+00:00",
                    "safety_level": "safe_read",
                    "attributes": {"semantic_type": "io"},
                },
            ),
            make_event(
                event_id=str(uuid.uuid4()),
                source_type="sdk",
                source_name="test",
                event_kind="run_end",
                payload={"run_id": run_id, "status": "completed", "ended_at": "2026-03-31T00:00:01+00:00"},
            ),
        ]
    )

    run = get_run(run_id)
    steps = list_steps_for_run(run_id)
    edges = list_edges_for_run(run_id)

    assert run is not None
    assert run.status == "completed"
    assert len(steps) == 1
    assert steps[0].safety_level == "safe_read"
    assert edges == []
