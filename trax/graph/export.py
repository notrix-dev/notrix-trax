"""Projection helpers for exporting persisted run graphs."""

from __future__ import annotations

from typing import Any

from trax.graph.builder import RunGraph
from trax.models import Run


def export_run_graph(run: Run, graph: RunGraph) -> dict[str, Any]:
    """Project a persisted run graph into a stable JSON-ready structure."""
    step_by_id = {step.id: step for step in graph.steps}
    ordered_steps = graph.topological_steps()

    nodes = [
        {
            "id": step.id,
            "name": step.name,
            "status": step.status,
            "position": step.position,
            "semantic_type": step.attributes.get("semantic_type"),
            "operation": step.attributes.get("operation_name"),
            "safety_level": str(step.safety_level),
            "scope_parent_step_id": step.attributes.get("scope_parent_step_id"),
            "source_type": step.attributes.get("source_type"),
            "started_at": step.started_at,
            "ended_at": step.ended_at,
            "input_artifact_ref": step.input_artifact_ref,
            "output_artifact_ref": step.output_artifact_ref,
            "error_message": step.error_message,
        }
        for step in ordered_steps
    ]

    edges = [
        {
            "id": edge.id,
            "source_step_id": edge.source_step_id,
            "target_step_id": edge.target_step_id,
            "type": str(edge.edge_type),
        }
        for edge in sorted(
            graph.edges,
            key=lambda edge: (
                step_by_id[edge.source_step_id].position,
                step_by_id[edge.target_step_id].position,
                str(edge.edge_type),
                edge.id,
            ),
        )
    ]

    return {
        "run": {
            "id": run.id,
            "name": run.name,
            "status": run.status,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "artifact_ref": run.artifact_ref,
            "error_message": run.error_message,
        },
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "root_count": len(graph.root_step_ids),
        },
    }
