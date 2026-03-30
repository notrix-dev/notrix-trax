"""Structured explanation engine result models."""

from __future__ import annotations

from dataclasses import dataclass

from trax.models import Explanation


@dataclass(frozen=True)
class ExplanationResult:
    run_id: str
    explanations: tuple[Explanation, ...]
