# Copyright 2026 Notrix LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Graph-aware deterministic diff engine."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from trax.diff.matcher import match_steps, step_type_for_match
from trax.diff.models import AttributeChange, DiffSummary, MetricDelta, RunDiff, StepDiff
from trax.graph import GraphValidationError, build_run_graph
from trax.models import Run, Step
from trax.storage import get_run, list_edges_for_run, list_steps_for_run
from trax.storage.artifacts import read_artifact


class DiffError(ValueError):
    """Raised when a diff cannot be produced safely."""


def diff_runs(before_run_id: str, after_run_id: str) -> RunDiff:
    """Load, compare, and summarize two runs."""
    before_run = get_run(before_run_id)
    after_run = get_run(after_run_id)
    if before_run is None:
        raise DiffError(f"Run not found: {before_run_id}")
    if after_run is None:
        raise DiffError(f"Run not found: {after_run_id}")

    try:
        before_graph = build_run_graph(
            before_run_id,
            list_steps_for_run(before_run_id),
            list_edges_for_run(before_run_id),
        )
        after_graph = build_run_graph(
            after_run_id,
            list_steps_for_run(after_run_id),
            list_edges_for_run(after_run_id),
        )
    except GraphValidationError as exc:
        raise DiffError(str(exc)) from exc

    matches, removed_steps, added_steps = match_steps(before_graph, after_graph)
    before_match_by_id = {match.before.id: match for match in matches}
    after_match_by_id = {match.after.id: match for match in matches}

    step_diffs: list[StepDiff] = []
    config_change_keys: set[str] = set()
    any_output_changed = False
    topology_changes: list[str] = []

    for match in matches:
        attribute_changes = _diff_attributes(match.before.attributes, match.after.attributes)
        input_changes: list[AttributeChange] = []
        output_changes: list[AttributeChange] = []
        reordered = match.before_index != match.after_index
        parent_changed = _parent_signature(match.before, before_match_by_id) != _parent_signature(
            match.after,
            after_match_by_id,
        )
        output_changed, output_missing = _artifact_changed(
            match.before.output_artifact_ref,
            match.after.output_artifact_ref,
        )
        input_changed, input_missing = _artifact_changed(
            match.before.input_artifact_ref,
            match.after.input_artifact_ref,
        )
        if input_changed and not input_missing:
            input_changes = _diff_artifact_payloads(
                match.before.input_artifact_ref,
                match.after.input_artifact_ref,
            )
        if output_changed and not output_missing:
            output_changes = _diff_artifact_payloads(
                match.before.output_artifact_ref,
                match.after.output_artifact_ref,
            )
        if reordered:
            topology_changes.append(f"step reordered: {match.before.name}")
        if parent_changed:
            topology_changes.append(f"parent/edge changed: {match.before.name}")

        if attribute_changes:
            config_change_keys.update(change.key for change in attribute_changes)
        if output_changed:
            any_output_changed = True

        modified = bool(attribute_changes or output_changed or parent_changed or reordered)
        step_diffs.append(
            StepDiff(
                status="MODIFIED" if modified else "UNCHANGED",
                before_step_id=match.before.id,
                after_step_id=match.after.id,
                before_name=match.before.name,
                after_name=match.after.name,
                before_position=match.before.position,
                after_position=match.after.position,
                step_type=step_type_for_match(match.after),
                attribute_changes=tuple(attribute_changes),
                input_changes=tuple(input_changes),
                output_changes=tuple(output_changes),
                output_changed=output_changed,
                output_missing=output_missing,
                parent_changed=parent_changed,
                reordered=reordered,
            )
        )

    for step in removed_steps:
        topology_changes.append(f"step removed: {step.name}")
        step_diffs.append(
            StepDiff(
                status="REMOVED",
                before_step_id=step.id,
                after_step_id=None,
                before_name=step.name,
                after_name=None,
                before_position=step.position,
                after_position=None,
                step_type=step_type_for_match(step),
            )
        )

    for step in added_steps:
        topology_changes.append(f"step added: {step.name}")
        step_diffs.append(
            StepDiff(
                status="ADDED",
                before_step_id=None,
                after_step_id=step.id,
                before_name=None,
                after_name=step.name,
                before_position=None,
                after_position=step.position,
                step_type=step_type_for_match(step),
            )
        )

    status_rank = {"MODIFIED": 0, "ADDED": 1, "REMOVED": 2, "UNCHANGED": 3}
    step_diffs.sort(
        key=lambda step_diff: (
            status_rank[step_diff.status],
            step_diff.after_position if step_diff.after_position is not None else 10_000,
            step_diff.before_position if step_diff.before_position is not None else 10_000,
            step_diff.display_name,
        )
    )

    metrics = _diff_metrics(before_run, after_run)
    return RunDiff(
        before_run_id=before_run_id,
        after_run_id=after_run_id,
        step_diffs=tuple(step_diffs),
        summary=DiffSummary(
            added_steps=sum(1 for step_diff in step_diffs if step_diff.status == "ADDED"),
            removed_steps=sum(1 for step_diff in step_diffs if step_diff.status == "REMOVED"),
            modified_steps=sum(1 for step_diff in step_diffs if step_diff.status == "MODIFIED"),
            unchanged_steps=sum(1 for step_diff in step_diffs if step_diff.status == "UNCHANGED"),
            output_changed=any_output_changed,
            key_config_changes=tuple(sorted(config_change_keys)),
        ),
        metrics=metrics,
        topology_changes=tuple(dict.fromkeys(topology_changes)),
    )


def _diff_attributes(before: dict[str, Any], after: dict[str, Any]) -> list[AttributeChange]:
    changes: list[AttributeChange] = []
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            changes.append(AttributeChange(key=key, before=before_value, after=after_value))
    return changes


def _parent_signature(step: Step, matches_by_step_id: dict[str, Any]) -> tuple[str | None, str | None]:
    if step.parent_step_id is None:
        return (None, None)

    matched_parent = matches_by_step_id.get(step.parent_step_id)
    if matched_parent is None:
        return ("unmatched-parent", step.parent_step_id)

    if step.id == matched_parent.before.id:
        parent_step = matched_parent.after
    else:
        parent_step = matched_parent.before
    return (parent_step.name, step_type_for_match(parent_step))


def _artifact_changed(before_ref: str | None, after_ref: str | None) -> tuple[bool, bool]:
    if before_ref is None and after_ref is None:
        return False, False

    before_payload, before_missing = _load_artifact(before_ref)
    after_payload, after_missing = _load_artifact(after_ref)
    if before_missing or after_missing:
        return before_payload != after_payload, True
    return _artifact_hash(before_payload) != _artifact_hash(after_payload), False


def _diff_artifact_payloads(before_ref: str | None, after_ref: str | None) -> list[AttributeChange]:
    before_payload, before_missing = _load_artifact(before_ref)
    after_payload, after_missing = _load_artifact(after_ref)
    if before_missing or after_missing:
        return []
    before_payload = _artifact_diff_payload(before_payload)
    after_payload = _artifact_diff_payload(after_payload)
    if not isinstance(before_payload, dict) or not isinstance(after_payload, dict):
        return []
    return _diff_payload_dicts(before_payload, after_payload)


def _artifact_diff_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and "preview" in payload:
        return payload["preview"]
    return payload


def _diff_nested_attributes(before: dict[str, Any], after: dict[str, Any]) -> list[AttributeChange]:
    changes: list[AttributeChange] = []
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, dict) and isinstance(after_value, dict):
            nested_changes = _diff_attributes(before_value, after_value)
            for nested_change in nested_changes:
                changes.append(
                    AttributeChange(
                        key=f"{key}.{nested_change.key}",
                        before=nested_change.before,
                        after=nested_change.after,
                    )
                )
    return changes


def _diff_payload_dicts(before: dict[str, Any], after: dict[str, Any]) -> list[AttributeChange]:
    changes: list[AttributeChange] = []
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, dict) and isinstance(after_value, dict):
            nested_changes = _diff_attributes(before_value, after_value)
            for nested_change in nested_changes:
                changes.append(
                    AttributeChange(
                        key=f"{key}.{nested_change.key}",
                        before=nested_change.before,
                        after=nested_change.after,
                    )
                )
        elif before_value != after_value:
            changes.append(AttributeChange(key=key, before=before_value, after=after_value))
    return changes


def _load_artifact(artifact_ref: str | None) -> tuple[Any, bool]:
    if artifact_ref is None:
        return None, False
    try:
        return read_artifact(artifact_ref), False
    except FileNotFoundError:
        return "missing", True


def _artifact_hash(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _diff_metrics(before_run: Run, after_run: Run) -> tuple[MetricDelta, ...]:
    before_metrics = _metrics_for_run(before_run)
    after_metrics = _metrics_for_run(after_run)
    metric_names = ["latency_ms", "tokens", "cost"]
    metrics: list[MetricDelta] = []
    for name in metric_names:
        before_value = before_metrics.get(name)
        after_value = after_metrics.get(name)
        delta = None
        if before_value is not None and after_value is not None:
            delta = after_value - before_value
        metrics.append(MetricDelta(name=name, before=before_value, after=after_value, delta=delta))
    return tuple(metrics)


def _metrics_for_run(run: Run) -> dict[str, float | int | None]:
    metrics: dict[str, float | int | None] = {
        "latency_ms": _duration_ms(run.started_at, run.ended_at),
        "tokens": None,
        "cost": None,
    }
    if run.artifact_ref is None:
        return metrics

    try:
        payload = read_artifact(run.artifact_ref)
    except FileNotFoundError:
        return metrics

    if isinstance(payload, dict):
        tokens = payload.get("tokens") or payload.get("token_count")
        cost = payload.get("cost")
        if isinstance(tokens, int | float):
            metrics["tokens"] = int(tokens) if isinstance(tokens, int) or float(tokens).is_integer() else float(tokens)
        if isinstance(cost, int | float):
            metrics["cost"] = float(cost)
    return metrics


def _duration_ms(started_at: str, ended_at: str | None) -> int | None:
    if ended_at is None:
        return None
    started = datetime.fromisoformat(started_at)
    ended = datetime.fromisoformat(ended_at)
    return int((ended - started).total_seconds() * 1000)
