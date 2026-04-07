"""Centralized semantic color helpers for the CLI."""

from __future__ import annotations

import os
import sys

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"


def color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def style(text: object, *codes: str) -> str:
    rendered = str(text)
    if not color_enabled() or not codes:
        return rendered
    return f"{''.join(codes)}{rendered}{RESET}"


def style_header(text: str) -> str:
    return style(f"{text}:", BOLD, WHITE)


def style_label(text: str) -> str:
    return style(text, DIM, BOLD)


def style_status(status: str) -> str:
    lowered = status.lower()
    if lowered in {"completed", "success"}:
        return style(status, GREEN)
    if lowered in {"failed", "error", "failed_safety_policy", "blocked"}:
        return style(status, RED)
    if lowered in {"partial", "warning", "unknown", "simulated", "modified"}:
        return style(status, YELLOW)
    if lowered in {"skipped", "unchanged"}:
        return style(status, DIM)
    if lowered in {"added"}:
        return style(status, GREEN)
    if lowered in {"removed"}:
        return style(status, RED)
    return status


def style_diff_kind(kind: str) -> str:
    if kind == "+":
        return style(kind, GREEN)
    if kind == "-":
        return style(kind, RED)
    if kind == "~":
        return style(kind, YELLOW)
    return style_status(kind)


def style_diff_step_name(step_name: str, kind: str) -> str:
    if kind == "+":
        return style(step_name, GREEN)
    if kind == "-":
        return style(step_name, RED)
    if kind == "~":
        return style(step_name, YELLOW)
    return step_name


def style_safety_level(level: str) -> str:
    lowered = level.lower()
    if lowered == "safe_read":
        return style(level, GREEN)
    if lowered == "unsafe_write":
        return style(level, RED, BOLD)
    return style(level, YELLOW)


def style_failure_header(text: str, *, has_failures: bool) -> str:
    if has_failures:
        return style(f"{text}:", RED, BOLD)
    return style(f"{text}:", GREEN, DIM)


def style_empty(text: str) -> str:
    return style(text, DIM)


def style_verdict(text: str, level: str) -> str:
    lowered = level.lower()
    if lowered in {"good", "stable", "positive"}:
        return style(text, GREEN)
    if lowered in {"warning", "changed", "caution"}:
        return style(text, YELLOW)
    if lowered in {"bad", "failed", "error"}:
        return style(text, RED)
    return str(text)


def style_verdict_line(text: str) -> str:
    return style(text, GREEN)


def style_step_name(step_name: str, semantic_type: str | None = None) -> str:
    semantic = semantic_type or _semantic_type_from_name(step_name)
    if semantic == "llm":
        return style(step_name, MAGENTA)
    if semantic == "retrieval":
        return style(step_name, CYAN)
    if semantic == "transform":
        return style(step_name, BLUE)
    if semantic == "reasoning":
        return style(step_name, YELLOW)
    if semantic == "tool":
        return style(step_name, GREEN)
    if semantic == "agent":
        return style(step_name, BOLD, WHITE)
    if semantic == "unknown":
        return style(step_name, DIM)
    return step_name


def _semantic_type_from_name(step_name: str) -> str | None:
    if ":" not in step_name:
        return None
    return step_name.split(":", 1)[0]
