"""Normalization from collected events into canonical persistence."""
# IMPORTANT:
# Explicit step scope MUST NOT be treated as structural parenthood.
# Structural edges must only come from:
# - dependency evidence
# - semantic relationships
# - validated sequential fallback

from __future__ import annotations

import json
import re
from typing import Any

from trax.collector import CollectedEvent
from trax.models import Edge, EdgeType, Run, SafetyLevel, SemanticType, Step
from trax.storage import bootstrap_local_storage
from trax.storage.artifacts import write_artifact
from trax.storage.repository import (
    insert_edge,
    insert_run,
    insert_step,
    update_run_completion,
)


def normalize_and_persist(events: list[CollectedEvent]) -> dict[str, Any]:
    """Normalize a collected event batch and persist canonical records."""
    bootstrap_local_storage()
    state: dict[str, Any] = {}
    seen_step_signatures_by_run: dict[str, set[str]] = {}
    for event in events:
        payload = event.payload
        if event.event_kind == "run_start":
            artifact_ref = write_artifact(payload["run_id"], "run-input", payload.get("input_payload"))
            run = Run(
                id=payload["run_id"],
                name=payload["name"],
                status="running",
                started_at=payload["started_at"],
                artifact_ref=artifact_ref,
            )
            insert_run(run)
            state[payload["run_id"]] = {}
        elif event.event_kind == "run_end":
            artifact_ref = write_artifact(payload["run_id"], "run-output", payload.get("output_payload"))
            update_run_completion(
                run_id=payload["run_id"],
                status=payload["status"],
                ended_at=payload["ended_at"],
                artifact_ref=artifact_ref,
                error_message=payload.get("error_message"),
            )
        elif event.event_kind == "step_end":
            run_id = payload["run_id"]
            seen_signatures = seen_step_signatures_by_run.setdefault(run_id, set())
            input_ref = write_artifact(payload["run_id"], f"step-{payload['position']}-input", payload.get("input_payload"))
            output_ref = write_artifact(payload["run_id"], f"step-{payload['position']}-output", payload.get("output_payload"))
            raw_attributes = dict(payload.get("attributes") or {})
            normalized_name, normalized_attributes = _normalize_step_identity(
                raw_name=payload["name"],
                source_type=payload.get("source_type"),
                default_source_type=event.source_type,
                attributes=raw_attributes,
            )
            dedup_signature = _step_dedup_signature(
                source_name=event.source_name,
                source_type=normalized_attributes.get("source_type"),
                semantic_type=normalized_attributes.get("semantic_type"),
                normalized_name=normalized_name,
                position=payload["position"],
                input_payload=payload.get("input_payload"),
                output_payload=payload.get("output_payload"),
            )
            if dedup_signature in seen_signatures:
                continue
            seen_signatures.add(dedup_signature)
            step = Step(
                id=payload["step_id"],
                run_id=run_id,
                name=normalized_name,
                status=payload["status"],
                position=payload["position"],
                started_at=payload["started_at"],
                ended_at=payload["ended_at"],
                safety_level=_coerce_safety_level(payload.get("safety_level")),
                parent_step_id=payload.get("parent_step_id"),
                input_artifact_ref=input_ref,
                output_artifact_ref=output_ref,
                attributes=normalized_attributes,
                error_message=payload.get("error_message"),
            )
            insert_step(step)
        elif event.event_kind == "edge":
            insert_edge(
                Edge(
                    id=payload["edge_id"],
                    run_id=payload["run_id"],
                    source_step_id=payload["source_step_id"],
                    target_step_id=payload["target_step_id"],
                    edge_type=EdgeType(payload["edge_type"]),
                )
            )
    return state


def _coerce_safety_level(value: object) -> SafetyLevel:
    if not isinstance(value, str) or not value:
        return SafetyLevel.UNKNOWN
    try:
        return SafetyLevel(value)
    except ValueError:
        return SafetyLevel.UNKNOWN


def _normalize_step_identity(
    *,
    raw_name: str,
    source_type: object,
    default_source_type: object,
    attributes: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    normalized_attributes = dict(attributes)
    normalized_attributes["source_type"] = _normalize_origin(source_type, default_source_type=default_source_type)
    normalized_attributes.setdefault("raw_name", raw_name)

    semantic_type = _coerce_semantic_type(normalized_attributes.get("semantic_type"), raw_name=raw_name)
    if semantic_type is None:
        semantic_type = SemanticType.UNKNOWN

    operation = _normalized_operation_name(
        semantic_type=semantic_type,
        raw_name=raw_name,
        operation_name=normalized_attributes.get("operation_name"),
    )
    normalized_attributes["semantic_type"] = semantic_type
    normalized_attributes["operation_name"] = operation
    return f"{semantic_type}:{operation}", normalized_attributes


def _normalize_origin(value: object, *, default_source_type: object) -> str:
    if value == "ergonomic":
        return "explicit"
    if isinstance(value, str) and value:
        return value
    if default_source_type == "import":
        return "import"
    return "unknown"


def _coerce_semantic_type(value: object, *, raw_name: str) -> SemanticType | None:
    if isinstance(value, str) and value:
        try:
            return SemanticType(value)
        except ValueError:
            if ":" not in raw_name:
                return SemanticType.UNKNOWN
            return None
    if ":" in raw_name:
        candidate = raw_name.split(":", 1)[0]
        try:
            return SemanticType(candidate)
        except ValueError:
            return None
    return None


def _normalized_operation_name(
    *,
    semantic_type: SemanticType,
    raw_name: str,
    operation_name: object,
) -> str:
    if isinstance(operation_name, str) and operation_name:
        cleaned = _clean_name_fragment(operation_name)
        if cleaned:
            return cleaned

    if ":" in raw_name:
        prefix, remainder = raw_name.split(":", 1)
        if prefix == semantic_type:
            cleaned = _clean_name_fragment(remainder)
            if cleaned:
                return cleaned

    cleaned_raw = _clean_name_fragment(raw_name)
    if cleaned_raw and cleaned_raw != semantic_type:
        return cleaned_raw

    return _fallback_operation_name(semantic_type)


def _clean_name_fragment(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = cleaned.replace("-", "_").replace(" ", "_")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def _fallback_operation_name(semantic_type: SemanticType) -> str:
    if semantic_type == SemanticType.LLM:
        return "call"
    if semantic_type == SemanticType.RETRIEVAL:
        return "query"
    if semantic_type == SemanticType.TOOL:
        return "call"
    if semantic_type == SemanticType.AGENT:
        return "step"
    if semantic_type == SemanticType.UNKNOWN:
        return "step"
    return "step"


def _step_dedup_signature(
    *,
    source_name: str,
    source_type: object,
    semantic_type: object,
    normalized_name: str,
    position: object,
    input_payload: object,
    output_payload: object,
) -> str:
    source_type_value = source_type if isinstance(source_type, str) and source_type else "unknown"
    semantic_type_value = semantic_type if isinstance(semantic_type, str) and semantic_type else "unknown"
    return json.dumps(
        {
            "source_name": source_name,
            "source_type": source_type_value,
            "semantic_type": semantic_type_value,
            "normalized_name": normalized_name,
            "position": position,
            "input": _stable_payload_signature(input_payload),
            "output": _stable_payload_signature(output_payload),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _stable_payload_signature(payload: object) -> object:
    try:
        return json.loads(json.dumps(payload, sort_keys=True, default=str))
    except TypeError:
        return repr(payload)
