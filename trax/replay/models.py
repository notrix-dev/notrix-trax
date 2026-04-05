# Copyright 2026 Notrix LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Structured replay result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplayStepResult:
    step_id: str
    step_name: str
    position: int
    status: str
    safety_level: str
    source: str
    detail: str


@dataclass(frozen=True)
class ReplayWindow:
    start_at: str | None
    stop_at: str | None
    effective_step_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReplayResult:
    run_id: str
    status: str
    window: ReplayWindow
    step_results: tuple[ReplayStepResult, ...]

    @property
    def simulated_count(self) -> int:
        return sum(1 for step in self.step_results if step.status == "SIMULATED")

    @property
    def blocked_count(self) -> int:
        return sum(1 for step in self.step_results if step.status == "BLOCKED")

    @property
    def skipped_count(self) -> int:
        return sum(1 for step in self.step_results if step.status == "SKIPPED")
