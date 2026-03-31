"""CLI entrypoint for the Trax foundation."""

from __future__ import annotations

import argparse
import sys

from trax.detect import DetectionError, analyze_run
from trax.diff import DiffError, diff_runs
from trax.explain import ExplainError, explain_run
from trax.graph import GraphValidationError, build_run_graph
from trax.replay import ReplayError, replay_run
from trax.storage import get_run, list_failures_for_run, list_steps_for_run
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
    diff_parser = subparsers.add_parser(
        "diff",
        help="Diff two captured runs.",
    )
    diff_parser.add_argument("run_id_1", help="The baseline run identifier.")
    diff_parser.add_argument("run_id_2", help="The comparison run identifier.")
    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay a captured run in simulation mode.",
    )
    replay_parser.add_argument("run_id", help="The captured run identifier.")
    explain_parser = subparsers.add_parser(
        "explain",
        help="Explain a captured run using persisted evidence.",
    )
    explain_parser.add_argument("run_id", help="The captured run identifier.")
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
    if args.command == "diff":
        return _diff_runs(args.run_id_1, args.run_id_2)
    if args.command == "replay":
        return _replay_run(args.run_id)
    if args.command == "explain":
        return _explain_run(args.run_id)

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
    try:
        failures = analyze_run(run_id)
    except DetectionError as exc:
        print(f"Detector Note: {exc}")
        failures = list_failures_for_run(run_id)
    print("Failures:")
    if not failures:
        print("  (none)")
    else:
        for failure in failures:
            print(f"  - [{failure.severity}/{failure.confidence}] {failure.kind}")
            print(f"    summary: {failure.summary}")
            if failure.step_id:
                print(f"    step_id: {failure.step_id}")
    return 0


def _diff_runs(run_id_1: str, run_id_2: str) -> int:
    try:
        result = diff_runs(run_id_1, run_id_2)
    except DiffError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Summary")
    print(f"  steps_added: {result.summary.added_steps}")
    print(f"  steps_removed: {result.summary.removed_steps}")
    print(f"  steps_modified: {result.summary.modified_steps}")
    print(f"  steps_unchanged: {result.summary.unchanged_steps}")
    print(f"  output_changed: {'yes' if result.summary.output_changed else 'no'}")
    if result.summary.key_config_changes:
        print(f"  key_config_changes: {', '.join(result.summary.key_config_changes)}")
    if result.topology_changes:
        print(f"  topology_changes: {len(result.topology_changes)}")

    print("Step Diff")
    for step_diff in result.step_diffs:
        print(f"[{step_diff.status}] {step_diff.display_name}")
        if step_diff.attribute_changes:
            print("  attrs:")
            for change in step_diff.attribute_changes:
                print(f"    {change.key}: {change.before} -> {change.after}")
        if step_diff.reordered:
            print(
                f"  traversal: {step_diff.before_position} -> {step_diff.after_position}"
            )
        if step_diff.parent_changed:
            print("  topology: parent/edge changed")
        if step_diff.output_missing:
            print("  output: missing")
        elif step_diff.output_changed:
            print("  output: changed")

    print("Metrics")
    for metric in result.metrics:
        if metric.delta is None:
            print(f"  {metric.name}: n/a")
            continue
        print(f"  {metric.name}: {_format_metric_delta(metric.name, metric.delta)}")
    return 0


def _replay_run(run_id: str) -> int:
    try:
        result = replay_run(run_id)
    except ReplayError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Replay: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Simulated Steps: {result.simulated_count}")
    print(f"Blocked Steps: {result.blocked_count}")
    for step in result.step_results:
        print(f"[{step.status}] {step.step_name}")
        print(f"  safety_level: {step.safety_level}")
        print(f"  source: {step.source}")
        print(f"  detail: {step.detail}")
    return 0


def _explain_run(run_id: str) -> int:
    try:
        result = explain_run(run_id)
    except ExplainError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Run: {result.run_id}")
    if not result.explanations:
        print("No issues detected.")
        return 0

    failures_by_id = {failure.id: failure for failure in list_failures_for_run(run_id)}
    steps_by_id = {step.id: step for step in list_steps_for_run(run_id)}
    for explanation in result.explanations:
        failure = failures_by_id.get(explanation.failure_id)
        print()
        print(f"Failure: {explanation.diagnosis}")
        if explanation.step_id and explanation.step_id in steps_by_id:
            print(f"Step: {steps_by_id[explanation.step_id].name}")
        elif failure is not None and failure.step_id:
            print(f"Step: {failure.step_id}")
        print("Likely causes:")
        for cause in explanation.likely_causes:
            print(f"- {cause}")
        print("Suggestions:")
        for suggestion in explanation.suggestions:
            print(f"- {_render_suggestion(suggestion, steps_by_id.get(explanation.step_id))}")
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


def _format_metric_delta(name: str, delta: float | int) -> str:
    if name == "latency_ms":
        return f"{delta:+.0f}ms"
    if name == "cost":
        return f"{delta:+.2f}"
    return f"{delta:+.0f}"


def _render_suggestion(suggestion: str, step: object) -> str:
    if suggestion == "increase top_k" and step is not None:
        current_top_k = getattr(step, "attributes", {}).get("top_k")
        if current_top_k is not None:
            return f"{suggestion} (current: {current_top_k})"
    return suggestion


if __name__ == "__main__":
    raise SystemExit(main())
