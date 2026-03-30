"""CLI entrypoint for the Trax foundation."""

from __future__ import annotations

import argparse
import sys

from trax.graph import GraphValidationError, build_run_graph
from trax.storage import get_run, list_steps_for_run
from trax.storage.repository import list_edges_for_run
from trax.storage.artifacts import read_artifact
from trax.storage.bootstrap import bootstrap_local_storage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trax",
        description="Local-first AI debugging CLI foundation.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the Trax foundation version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect a captured run.",
    )
    inspect_parser.add_argument("run_id", help="The captured run identifier.")
    return parser


def main() -> int:
    parser = build_parser()
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        return int(exc.code)

    if args.version:
        from trax import __version__

        print(__version__)
        return 0

    try:
        bootstrap_local_storage()
    except PermissionError as exc:
        print(f"Unable to initialize local Trax storage: {exc}", file=sys.stderr)
        return 1

    if args.command == "inspect":
        return _inspect_run(args.run_id)

    return 0


def _inspect_run(run_id: str) -> int:
    run = get_run(run_id)
    if run is None:
        print(f"Run not found: {run_id}", file=sys.stderr)
        return 1

    print(f"Run: {run.id}")
    print(f"Name: {run.name}")
    print(f"Status: {run.status}")
    print(f"Started: {run.started_at}")
    print(f"Ended: {run.ended_at or '-'}")
    if run.artifact_ref:
        print(f"Run Artifact: {run.artifact_ref}")
        print(f"Run Artifact Summary: {_summarize_artifact(run.artifact_ref)}")
    if run.error_message:
        print(f"Run Error: {run.error_message}")

    steps = list_steps_for_run(run_id)
    edges = list_edges_for_run(run_id)
    print(f"Steps: {len(steps)}")
    try:
        graph = build_run_graph(run_id, steps, edges)
    except GraphValidationError as exc:
        print(f"Graph Error: {exc}", file=sys.stderr)
        return 1

    for step in graph.topological_steps():
        print(f"- [{step.position}] {step.name} ({step.status})")
        if step.input_artifact_ref:
            print(f"  input: {step.input_artifact_ref}")
            print(f"  input_summary: {_summarize_artifact(step.input_artifact_ref)}")
        if step.output_artifact_ref:
            print(f"  output: {step.output_artifact_ref}")
            print(f"  output_summary: {_summarize_artifact(step.output_artifact_ref)}")
        if step.attributes:
            print(f"  attributes: {step.attributes}")
        if step.error_message:
            print(f"  error: {step.error_message}")
    print("Graph:")
    if not graph.steps:
        print("  (empty)")
    else:
        for line in _render_graph(graph):
            print(line)
    return 0


def _summarize_artifact(artifact_ref: str) -> str:
    try:
        payload = read_artifact(artifact_ref)
    except FileNotFoundError:
        return "missing"

    if isinstance(payload, dict):
        keys = ", ".join(sorted(payload.keys()))
        return f"object keys=[{keys}]" if keys else "object"
    if isinstance(payload, list):
        return f"list len={len(payload)}"
    return repr(payload)


def _render_graph(graph: object) -> list[str]:
    lines: list[str] = []
    visited: set[str] = set()
    step_by_id = {step.id: step for step in graph.steps}

    def visit(step_id: str, depth: int) -> None:
        if step_id in visited:
            return
        visited.add(step_id)
        node = graph.nodes[step_id]
        step = node.step
        indent = "  " * depth
        relation = "root" if node.parent_step_id is None else f"parent={node.parent_step_id}"
        lines.append(f"{indent}- [{step.position}] {step.name} ({relation})")
        for child_step_id in node.child_step_ids:
            visit(child_step_id, depth + 1)

    for root_step_id in graph.root_step_ids:
        visit(root_step_id, 1)

    orphaned = [step for step in graph.steps if step.id not in visited]
    for step in orphaned:
        lines.append(f"  - [{step.position}] {step.name} (disconnected)")

    control_flow_edges = [
        edge for edge in graph.edges if edge.edge_type == "control_flow"
    ]
    if control_flow_edges:
        lines.append("  Control Flow:")
        for edge in control_flow_edges:
            source = step_by_id[edge.source_step_id]
            target = step_by_id[edge.target_step_id]
            lines.append(f"    - [{source.position}] {source.name} -> [{target.position}] {target.name}")

    return lines


if __name__ == "__main__":
    raise SystemExit(main())
