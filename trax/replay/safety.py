"""Centralized replay safety policy checks."""

from __future__ import annotations

from trax.models import Step


def safety_level_for_step(step: Step) -> str:
    raw_value = step.attributes.get("safety_level")
    if isinstance(raw_value, str) and raw_value:
        return raw_value
    return "unknown"


def blocked_reason_for_step(step: Step) -> str | None:
    safety_level = safety_level_for_step(step)
    if safety_level == "unsafe_write":
        return "blocked by replay safety policy: unsafe_write"
    if safety_level == "unknown":
        return "blocked by replay safety policy: unknown safety level"
    return None
