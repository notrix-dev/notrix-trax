"""Reusable plain-text CLI formatting helpers."""

from __future__ import annotations


def section(title: str) -> str:
    return f"{title}:"


def field(label: str, value: object) -> str:
    return f"{label}: {value}"


def bullet(text: str, indent: int = 0) -> str:
    return f"{'  ' * indent}- {text}"


def empty_state(message: str) -> str:
    return message
