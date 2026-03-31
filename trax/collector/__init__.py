"""In-process collection boundary for raw capture events."""

from __future__ import annotations

from trax.collector.events import CollectedEvent, make_event


class InProcessCollector:
    """Collect raw events without assigning semantics."""

    def __init__(self) -> None:
        self._events: list[CollectedEvent] = []

    def collect(self, event: CollectedEvent) -> None:
        self._events.append(event)

    def flush(self) -> list[CollectedEvent]:
        events = list(self._events)
        self._events.clear()
        return events


__all__ = ["CollectedEvent", "InProcessCollector", "make_event"]
