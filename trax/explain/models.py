"""Structured explanation engine result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Explanation:
    run_id: str
    failure_id: str
    diagnosis: str
    step_id: str | None
    likely_causes: tuple[str, ...]
    suggestions: tuple[str, ...]


@dataclass(frozen=True)
class ExplanationResult:
    run_id: str
    explanations: tuple[Explanation, ...]
