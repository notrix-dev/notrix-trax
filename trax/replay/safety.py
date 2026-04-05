# Copyright 2026 Notrix LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Centralized replay safety policy checks."""

from __future__ import annotations

from trax.models import SafetyLevel, Step


def safety_level_for_step(step: Step) -> SafetyLevel:
    return step.safety_level or SafetyLevel.UNKNOWN


def blocked_reason_for_step(step: Step) -> str | None:
    safety_level = safety_level_for_step(step)
    if safety_level == SafetyLevel.UNSAFE_WRITE:
        return "blocked by replay safety policy: unsafe_write"
    if safety_level == SafetyLevel.UNKNOWN:
        return "blocked by replay safety policy: unknown safety level"
    return None
