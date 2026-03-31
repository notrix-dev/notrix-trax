"""Minimal retrieval adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from trax.sdk import end_run, has_active_run, start_run, trace_step


def traced_retrieval(
    *,
    query: str,
    top_k: int,
    backend: str,
    retrieve: Callable[..., list[Any]] | None = None,
    run_name: str = "retrieval",
    step_name: str = "retrieval:query",
    **kwargs: Any,
) -> list[Any]:
    """Trace a minimal retrieval call."""
    created_run = False
    if not has_active_run():
        start_run(
            run_name,
            input_payload={"query": query, "top_k": top_k, "backend": backend, "kwargs": kwargs},
            source_type="passive",
            capture_policy="summary",
        )
        created_run = True

    error_message: str | None = None
    docs: list[Any] | None = None
    try:
        docs = retrieve(query=query, top_k=top_k, backend=backend, **kwargs) if retrieve is not None else []
        return docs
    except Exception as exc:
        error_message = str(exc)
        raise
    finally:
        trace_step(
            step_name,
            input_payload={"query": query},
            output_payload=docs,
            attributes={
                "semantic_type": "retrieval",
                "top_k": top_k,
                "backend": backend,
            },
            error_message=error_message,
        )
        if created_run:
            end_run(output_payload={"documents": docs}, error_message=error_message)
