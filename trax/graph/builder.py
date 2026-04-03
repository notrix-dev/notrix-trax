"""Per-run execution graph reconstruction helpers."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from trax.models import Edge, EdgeType, Step


class GraphValidationError(ValueError):
    """Raised when persisted graph data cannot form a safe per-run DAG."""


@dataclass(frozen=True)
class StepNode:
    """Graph view of a captured step."""

    step: Step
    parent_step_id: str | None
    child_step_ids: tuple[str, ...]
    incoming_step_ids: tuple[str, ...]
    outgoing_step_ids: tuple[str, ...]


@dataclass(frozen=True)
class RunGraph:
    """Materialized graph for a single run."""

    run_id: str
    steps: tuple[Step, ...]
    edges: tuple[Edge, ...]
    nodes: dict[str, StepNode] = field(repr=False)
    root_step_ids: tuple[str, ...]

    def topological_steps(self) -> list[Step]:
        in_degree = {step.id: 0 for step in self.steps}
        outgoing: dict[str, list[str]] = defaultdict(list)
        position_by_step_id = {step.id: step.position for step in self.steps}

        for edge in self.edges:
            outgoing[edge.source_step_id].append(edge.target_step_id)
            in_degree[edge.target_step_id] += 1

        queue = deque(
            sorted(
                (step.id for step in self.steps if in_degree[step.id] == 0),
                key=lambda step_id: position_by_step_id[step_id],
            )
        )
        ordered_ids: list[str] = []
        while queue:
            step_id = queue.popleft()
            ordered_ids.append(step_id)
            for target_step_id in sorted(
                outgoing[step_id],
                key=lambda current_step_id: position_by_step_id[current_step_id],
            ):
                in_degree[target_step_id] -= 1
                if in_degree[target_step_id] == 0:
                    queue.append(target_step_id)

        if len(ordered_ids) != len(self.steps):
            raise GraphValidationError(f"Cycle detected in run graph: {self.run_id}")

        step_by_id = {step.id: step for step in self.steps}
        return [step_by_id[step_id] for step_id in ordered_ids]


def build_run_graph(run_id: str, steps: list[Step], edges: list[Edge]) -> RunGraph:
    """Build and validate a per-run DAG from persisted steps and edges."""
    step_by_id = {step.id: step for step in steps}
    incoming_by_step_id: dict[str, list[str]] = defaultdict(list)
    outgoing_by_step_id: dict[str, list[str]] = defaultdict(list)

    for step in steps:
        if step.run_id != run_id:
            raise GraphValidationError(
                f"Step {step.id} belongs to run {step.run_id}, expected {run_id}"
            )

    seen_edges: set[tuple[str, str, str]] = set()
    for edge in edges:
        if edge.run_id != run_id:
            raise GraphValidationError(
                f"Edge {edge.id} belongs to run {edge.run_id}, expected {run_id}"
            )
        if edge.source_step_id not in step_by_id or edge.target_step_id not in step_by_id:
            raise GraphValidationError(f"Edge {edge.id} references missing step(s)")

        source_step = step_by_id[edge.source_step_id]
        target_step = step_by_id[edge.target_step_id]
        if source_step.run_id != run_id or target_step.run_id != run_id:
            raise GraphValidationError(f"Edge {edge.id} crosses run boundaries")

        edge_key = (edge.source_step_id, edge.target_step_id, edge.edge_type)
        if edge_key in seen_edges:
            raise GraphValidationError(
                f"Duplicate edge detected: {edge.source_step_id} -> {edge.target_step_id} ({edge.edge_type})"
            )
        seen_edges.add(edge_key)

        outgoing_by_step_id[edge.source_step_id].append(edge.target_step_id)
        incoming_by_step_id[edge.target_step_id].append(edge.source_step_id)

    nodes = {
        step.id: StepNode(
            step=step,
            parent_step_id=None,
            child_step_ids=tuple(
                sorted(
                    [
                        edge.target_step_id
                        for edge in edges
                        if edge.edge_type == EdgeType.PARENT_CHILD and edge.source_step_id == step.id
                    ],
                    key=lambda step_id: step_by_id[step_id].position,
                )
            ),
            incoming_step_ids=tuple(
                sorted(incoming_by_step_id.get(step.id, []), key=lambda step_id: step_by_id[step_id].position)
            ),
            outgoing_step_ids=tuple(
                sorted(outgoing_by_step_id.get(step.id, []), key=lambda step_id: step_by_id[step_id].position)
            ),
        )
        for step in sorted(steps, key=lambda current_step: current_step.position)
    }

    graph = RunGraph(
        run_id=run_id,
        steps=tuple(sorted(steps, key=lambda step: step.position)),
        edges=tuple(edges),
        nodes=nodes,
        root_step_ids=tuple(
            step.id
            for step in sorted(steps, key=lambda step: step.position)
            if not incoming_by_step_id.get(step.id)
        ),
    )
    graph.topological_steps()
    return graph
