# Copyright 2026 Notrix LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Structured diff result models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AttributeChange:
    key: str
    before: object | None
    after: object | None


@dataclass(frozen=True)
class StepDiff:
    status: str
    before_step_id: str | None
    after_step_id: str | None
    before_name: str | None
    after_name: str | None
    before_position: int | None
    after_position: int | None
    step_type: str | None
    attribute_changes: tuple[AttributeChange, ...] = ()
    output_changed: bool = False
    output_missing: bool = False
    parent_changed: bool = False
    reordered: bool = False

    @property
    def display_name(self) -> str:
        return self.after_name or self.before_name or "unknown-step"


@dataclass(frozen=True)
class MetricDelta:
    name: str
    before: float | int | None
    after: float | int | None
    delta: float | int | None


@dataclass(frozen=True)
class DiffSummary:
    added_steps: int
    removed_steps: int
    modified_steps: int
    unchanged_steps: int
    output_changed: bool
    key_config_changes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunDiff:
    before_run_id: str
    after_run_id: str
    step_diffs: tuple[StepDiff, ...]
    summary: DiffSummary
    metrics: tuple[MetricDelta, ...]
    topology_changes: tuple[str, ...] = field(default_factory=tuple)
