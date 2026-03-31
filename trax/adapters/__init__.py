"""Thin adapters for common AI workflow entrypoints."""

from .openai import traced_chat
from .otel import import_trace
from .retrieval import traced_retrieval

__all__ = ["import_trace", "traced_chat", "traced_retrieval"]
