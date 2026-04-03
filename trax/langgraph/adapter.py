"""Real LangGraph execution-boundary helpers."""

from __future__ import annotations

from functools import wraps
from typing import Any

from trax.sdk import end_run, has_active_run, start_run, trace_step


def _validate_compiled_langgraph(graph: object) -> None:
    try:
        from langgraph.graph.state import CompiledStateGraph
    except ImportError as exc:  # pragma: no cover - guarded by packaging/tests
        raise RuntimeError(
            "LangGraph is not installed. Install 'langgraph' to use trax.langgraph."
        ) from exc

    if not isinstance(graph, CompiledStateGraph):
        raise TypeError(
            "traced_invoke expects a real LangGraph compiled graph object "
            "(langgraph.graph.state.CompiledStateGraph)."
        )


def traced_invoke(graph: object, input_payload: dict[str, Any], *, run_name: str = "langgraph-basic") -> Any:
    """Invoke a real compiled LangGraph graph while Trax captures the run."""
    _validate_compiled_langgraph(graph)

    started_here = False
    if not has_active_run():
        start_run(
            run_name,
            input_payload=input_payload,
            source_type="passive",
            capture_policy="summary",
        )
        started_here = True

    error_message: str | None = None
    result: Any = None
    try:
        result = graph.invoke(input_payload)
        return result
    except Exception as exc:
        error_message = str(exc)
        raise
    finally:
        if started_here:
            end_run(output_payload=result, error_message=error_message)


def traced_node(
    step_name: str,
    *,
    semantic_type: str = "agent",
    attributes: dict[str, Any] | None = None,
) -> Any:
    """Trace a real node execution boundary during graph invocation."""
    base_attributes = dict(attributes or {})
    base_attributes.setdefault("semantic_type", semantic_type)
    base_attributes.setdefault("safety_level", "safe_read")
    base_attributes.setdefault("source_type", "passive")

    def decorator(func: Any) -> Any:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            error_message: str | None = None
            result: Any = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as exc:
                error_message = str(exc)
                raise
            finally:
                trace_step(
                    step_name,
                    input_payload={"args": list(args), "kwargs": kwargs},
                    output_payload=result,
                    attributes=base_attributes,
                    error_message=error_message,
                )

        wrapper.__trax_node__ = {
            "step_name": step_name,
            "semantic_type": semantic_type,
            "attributes": dict(base_attributes),
        }
        return wrapper

    return decorator
