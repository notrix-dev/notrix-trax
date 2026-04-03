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
    assert steps[0].name == "io:fetch"
    assert steps[0].attributes["source_type"] == "unknown"
    assert steps[0].attributes["operation_name"] == "fetch"
    assert edges == []


def test_normalizer_uses_conservative_domain_fallback_when_operation_is_unstable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run_id = str(uuid.uuid4())

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
                    "step_id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "name": "llm",
                    "status": "completed",
                    "position": 1,
                    "started_at": "2026-03-31T00:00:00+00:00",
                    "ended_at": "2026-03-31T00:00:01+00:00",
                    "attributes": {"semantic_type": "llm", "source_type": "passive"},
                },
            ),
        ]
    )

    steps = list_steps_for_run(run_id)
    assert len(steps) == 1
    assert steps[0].name == "llm:call"
    assert steps[0].attributes["operation_name"] == "call"


def test_normalizer_namespaces_unknown_domains_conservatively(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run_id = str(uuid.uuid4())

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
                    "step_id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "name": "searchDocuments",
                    "status": "completed",
                    "position": 1,
                    "started_at": "2026-03-31T00:00:00+00:00",
                    "ended_at": "2026-03-31T00:00:01+00:00",
                    "attributes": {},
                },
            ),
        ]
    )

    steps = list_steps_for_run(run_id)
    assert len(steps) == 1
    assert steps[0].name == "unknown:searchdocuments"
    assert steps[0].attributes["semantic_type"] == "unknown"


def test_normalizer_deduplicates_identical_semantic_events_conservatively(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run_id = str(uuid.uuid4())

    duplicate_payload = {
        "run_id": run_id,
        "name": "faq_search",
        "status": "completed",
        "position": 1,
        "started_at": "2026-03-31T00:00:00+00:00",
        "ended_at": "2026-03-31T00:00:01+00:00",
        "input_payload": {"query": "hello"},
        "output_payload": {"docs": [{"id": "doc-1"}]},
        "attributes": {"semantic_type": "retrieval"},
    }

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
                source_type="passive",
                source_name="retrieval-adapter",
                event_kind="step_end",
                payload={"step_id": str(uuid.uuid4()), **duplicate_payload},
            ),
            make_event(
                event_id=str(uuid.uuid4()),
                source_type="passive",
                source_name="retrieval-adapter",
                event_kind="step_end",
                payload={"step_id": str(uuid.uuid4()), **duplicate_payload},
            ),
        ]
    )

    steps = list_steps_for_run(run_id)
    assert len(steps) == 1
    assert steps[0].name == "retrieval:faq_search"


def test_normalizer_assigns_occurrence_indexes_within_parent_scope(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid4())

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
                    "step_id": parent_id,
                    "run_id": run_id,
                    "name": "prepare-input",
                    "status": "completed",
                    "position": 1,
                    "started_at": "2026-03-31T00:00:00+00:00",
                    "ended_at": "2026-03-31T00:00:01+00:00",
                    "attributes": {"semantic_type": "transform"},
                },
            ),
            make_event(
                event_id=str(uuid.uuid4()),
                source_type="sdk",
                source_name="test",
                event_kind="step_end",
                payload={
                    "step_id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "name": "faq_search",
                    "status": "completed",
                    "position": 2,
                    "parent_step_id": parent_id,
                    "started_at": "2026-03-31T00:00:01+00:00",
                    "ended_at": "2026-03-31T00:00:02+00:00",
                    "attributes": {"semantic_type": "retrieval"},
                },
            ),
            make_event(
                event_id=str(uuid.uuid4()),
                source_type="sdk",
                source_name="test",
                event_kind="step_end",
                payload={
                    "step_id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "name": "faq_search",
                    "status": "completed",
                    "position": 3,
                    "parent_step_id": parent_id,
                    "started_at": "2026-03-31T00:00:02+00:00",
                    "ended_at": "2026-03-31T00:00:03+00:00",
                    "attributes": {"semantic_type": "retrieval"},
                },
            ),
        ]
    )

    steps = list_steps_for_run(run_id)
    child_steps = [step for step in steps if step.parent_step_id == parent_id]
    assert [step.name for step in child_steps] == ["retrieval:faq_search", "retrieval:faq_search"]
    assert all("occurrence_index" not in step.attributes for step in child_steps)
