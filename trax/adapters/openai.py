"""Minimal OpenAI-style adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from trax.sdk import end_run, has_active_run, start_run, trace_step


def traced_chat(
    *,
    model: str,
    messages: list[dict[str, Any]],
    call: Callable[..., Any] | None = None,
    run_name: str = "openai-chat",
    step_name: str = "llm:chat",
    **kwargs: Any,
) -> Any:
    """Trace a minimal OpenAI chat-style call."""
    created_run = False
    if not has_active_run():
        start_run(
            run_name,
            input_payload={"model": model, "messages": messages, "kwargs": kwargs},
            source_type="passive",
            capture_policy="summary",
        )
        created_run = True

    error_message: str | None = None
    response: Any = None
    try:
        response = call(model=model, messages=messages, **kwargs) if call is not None else {
            "model": model,
            "output_text": "",
        }
        return response
    except Exception as exc:
        error_message = str(exc)
        raise
    finally:
        trace_step(
            step_name,
            input_payload={"messages": messages},
            output_payload=response,
            attributes=_chat_attributes(model=model, response=response, extra=kwargs),
            error_message=error_message,
        )
        if created_run:
            end_run(output_payload=response, error_message=error_message)


def _chat_attributes(*, model: str, response: Any, extra: dict[str, Any]) -> dict[str, Any]:
    attributes: dict[str, Any] = {"semantic_type": "llm", "model": model}
    usage = response.get("usage") if isinstance(response, dict) else None
    if isinstance(usage, dict):
        total_tokens = usage.get("total_tokens")
        if isinstance(total_tokens, int | float):
            attributes["tokens"] = int(total_tokens)
    for key in ("temperature", "max_tokens"):
        value = extra.get(key)
        if value is not None:
            attributes[key] = value
    return attributes
