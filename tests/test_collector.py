"""Collector ingestion tests for v1.5 alignment foundation."""

from __future__ import annotations

import uuid

from trax.collector import InProcessCollector, make_event


def test_collector_buffers_and_flushes_events() -> None:
    collector = InProcessCollector()
    event = make_event(
        event_id=str(uuid.uuid4()),
        source_type="sdk",
        source_name="test",
        event_kind="run_start",
        payload={"run_id": "run-1", "name": "demo", "started_at": "2026-03-31T00:00:00+00:00"},
    )

    collector.collect(event)

    events = collector.flush()
    assert len(events) == 1
    assert events[0].event_kind == "run_start"
    assert collector.flush() == []
