"""Reusable plain-text CLI formatting helpers."""

from __future__ import annotations

from trax.cli.theme import style_empty, style_header, style_label, style_verdict_line


def section(title: str) -> str:
    return style_header(title)


def field(label: str, value: object) -> str:
    return f"{style_label(label)}: {value}"


def bullet(text: str, indent: int = 0) -> str:
    return f"{'  ' * indent}- {text}"


def empty_state(message: str) -> str:
    return style_empty(message)


def verdict(message: str) -> str:
    return style_verdict_line(f"Verdict: {message}")
