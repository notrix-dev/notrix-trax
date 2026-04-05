# Copyright 2026 Notrix LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Detector engine orchestration."""

from __future__ import annotations

from trax.detect.rules import detect_failures
from trax.graph import GraphValidationError, build_run_graph
from trax.models import Failure
from trax.storage import (
    get_run,
    list_edges_for_run,
    list_failures_for_run,
    list_steps_for_run,
    replace_failures_for_run,
)


class DetectionError(ValueError):
    """Raised when a run cannot be analyzed safely."""


def analyze_run(run_id: str) -> list[Failure]:
    """Analyze a run, persist fresh failures, and return them."""
    run = get_run(run_id)
    if run is None:
        raise DetectionError(f"Run not found: {run_id}")

    try:
        graph = build_run_graph(run_id, list_steps_for_run(run_id), list_edges_for_run(run_id))
    except GraphValidationError as exc:
        raise DetectionError(str(exc)) from exc

    failures = detect_failures(run, graph)
    replace_failures_for_run(run_id, failures)
    return list_failures_for_run(run_id)
