# Copyright 2026 Notrix LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Deterministic step matching for graph-aware run diff."""

from __future__ import annotations

from dataclasses import dataclass

from trax.graph import RunGraph
from trax.models import SemanticType, Step


@dataclass(frozen=True)
class MatchedSteps:
    before: Step
    after: Step
    before_index: int
    after_index: int


def step_type_for_match(step: Step) -> str:
    """Return the stable v1 step type heuristic used for matching."""
    semantic_type = step.attributes.get("semantic_type")
    if isinstance(semantic_type, str) and semantic_type:
        try:
            return SemanticType(semantic_type)
        except ValueError:
            return semantic_type
    if ":" in step.name:
        return step.name.split(":", 1)[0]
    return "generic"


def match_steps(before_graph: RunGraph, after_graph: RunGraph) -> tuple[list[MatchedSteps], list[Step], list[Step]]:
    """Match steps deterministically using name, type, and traversal order."""
    before_steps = before_graph.topological_steps()
    after_steps = after_graph.topological_steps()
    after_candidates_by_signature: dict[tuple[str, str], list[tuple[int, Step]]] = {}

    for index, step in enumerate(after_steps):
        signature = (step.name, step_type_for_match(step))
        after_candidates_by_signature.setdefault(signature, []).append((index, step))

    matches: list[MatchedSteps] = []
    matched_after_ids: set[str] = set()

    for before_index, before_step in enumerate(before_steps):
        signature = (before_step.name, step_type_for_match(before_step))
        candidates = after_candidates_by_signature.get(signature, [])
        available_candidates = [
            (candidate_index, candidate_step)
            for candidate_index, candidate_step in candidates
            if candidate_step.id not in matched_after_ids
        ]
        if not available_candidates:
            continue

        after_index, after_step = min(
            available_candidates,
            key=lambda item: (abs(item[0] - before_index), item[0]),
        )
        matched_after_ids.add(after_step.id)
        matches.append(
            MatchedSteps(
                before=before_step,
                after=after_step,
                before_index=before_index,
                after_index=after_index,
            )
        )

    matched_before_ids = {match.before.id for match in matches}
    removed_steps = [step for step in before_steps if step.id not in matched_before_ids]
    added_steps = [step for step in after_steps if step.id not in matched_after_ids]
    return matches, removed_steps, added_steps
