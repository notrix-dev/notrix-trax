"""CLI entrypoint for the Trax foundation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trax.adapters.otel import import_trace
from trax.cli.formatters import bullet, empty_state, field, section
from trax.detect import DetectionError, analyze_run
from trax.diff import DiffError, diff_runs
from trax.explain import ExplainError, explain_run
from trax.graph import GraphValidationError, build_run_graph, export_run_graph
from trax.models import EdgeType, SemanticType
from trax.replay import ReplayError, replay_run
from trax.storage import get_run, list_failures_for_run, list_runs, list_steps_for_run
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
    import_parser = subparsers.add_parser(
        "import-otel",
        help="Import a basic OTel trace JSON file.",
    )
    import_parser.add_argument("trace_path", help="Path to the OTel trace JSON file.")
    list_parser = subparsers.add_parser(
        "list",
        help="List recent captured runs.",
    )
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum number of runs to show.")
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect a captured run.",
    )
    inspect_parser.add_argument("run_id", help="The captured run identifier.")
    inspect_parser.add_argument("--step-type", dest="step_type", help="Filter steps by semantic type.")
    inspect_parser.add_argument("--step-name", dest="step_name", help="Filter steps by exact step name.")
    inspect_parser.add_argument("--step-status", dest="step_status", help="Filter steps by persisted status.")
    graph_parser = subparsers.add_parser(
        "graph",
        help="Export a captured run graph.",
    )
    graph_parser.add_argument("--run-id", required=True, dest="run_id", help="The captured run identifier.")
    graph_parser.add_argument("--format", default="json", dest="output_format", help="Export format. Launch scope: json.")
    graph_parser.add_argument("--output", dest="output_path", help="Optional file path for exported graph JSON.")
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
    replay_parser.add_argument("--start-at", dest="start_at", help="Replay starting step id.")
    replay_parser.add_argument("--stop-at", dest="stop_at", help="Replay ending step id.")
    explain_parser = subparsers.add_parser(
        "explain",
        help="Explain a captured run using persisted evidence.",
    )
    explain_parser.add_argument("run_id", help="The captured run identifier.")
    explain_parser.add_argument("--failure-kind", dest="failure_kind", help="Filter explanations by failure kind.")
    explain_parser.add_argument("--severity", dest="severity", help="Filter explanations by failure severity.")
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

    if args.command == "import-otel":
        return _import_otel(args.trace_path)
    if args.command == "list":
        return _list_runs(args.limit)
    if args.command == "inspect":
        return _inspect_run(
            args.run_id,
            step_type=args.step_type,
            step_name=args.step_name,
            step_status=args.step_status,
        )
    if args.command == "graph":
        return _export_graph(args.run_id, output_format=args.output_format, output_path=args.output_path)
    if args.command == "diff":
        return _diff_runs(args.run_id_1, args.run_id_2)
    if args.command == "replay":
        return _replay_run(args.run_id, start_at=args.start_at, stop_at=args.stop_at)
    if args.command == "explain":
        return _explain_run(args.run_id, failure_kind=args.failure_kind, severity=args.severity)

    return 0


def _export_graph(run_id: str, *, output_format: str, output_path: str | None) -> int:
    if output_format != "json":
        print(f"Unsupported graph export format: {output_format}", file=sys.stderr)
        return 1

    run = get_run(run_id)
    if run is None:
        print(f"Run not found: {run_id}", file=sys.stderr)
        return 1

    steps = list_steps_for_run(run_id)
    edges = list_edges_for_run(run_id)
    try:
        graph = build_run_graph(run_id, steps, edges)
    except GraphValidationError as exc:
        print(f"Graph Error: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(export_run_graph(run, graph), indent=2, sort_keys=True)
    if output_path:
        Path(output_path).write_text(rendered + "\n", encoding="utf-8")
        return 0

    print(rendered)
    return 0


def _list_runs(limit: int) -> int:
    runs = list_runs(limit=max(1, limit))
    print(section("Runs"))
    if not runs:
        print(empty_state("No runs found."))
        return 0

    for run in runs:
        print(bullet(run.id))
        print(field("  Name", run.name))
        print(field("  Status", run.status))
        print(field("  Started", run.started_at))
    return 0


def _import_otel(trace_path: str) -> int:
    try:
        run_id = import_trace(trace_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(section("OTel Import"))
    print(field("Run", run_id))
    return 0


def _inspect_run(
    run_id: str,
    *,
    step_type: str | None = None,
    step_name: str | None = None,
    step_status: str | None = None,
) -> int:
    run = get_run(run_id)
    if run is None:
        print(f"Run not found: {run_id}", file=sys.stderr)
        return 1

    print(section("Run"))
    print(field("Run", run.id))
    print(field("Name", run.name))
    print(field("Status", run.status))
    print(field("Started", run.started_at))
    print(field("Ended", run.ended_at or "-"))
    if run.artifact_ref:
        print(field("Run Artifact", run.artifact_ref))
        print(field("Run Artifact Summary", _summarize_artifact(run.artifact_ref)))
    if run.error_message:
        print(field("Run Error", run.error_message))

    steps = list_steps_for_run(run_id)
    edges = list_edges_for_run(run_id)
    print(field("Steps", len(steps)))
    try:
        graph = build_run_graph(run_id, steps, edges)
    except GraphValidationError as exc:
        print(f"Graph Error: {exc}", file=sys.stderr)
        return 1

    filtered_steps = _filter_steps(
        graph.topological_steps(),
        step_type=step_type,
        step_name=step_name,
        step_status=step_status,
    )
    display_names = _display_name_by_step_id(graph.steps)
    filtered_step_ids = {step.id for step in filtered_steps}
    print(section("Step Details"))
    if not filtered_steps:
        print(empty_state(_no_steps_message(step_type=step_type, step_name=step_name, step_status=step_status)))
    for step in filtered_steps:
        print(bullet(f"[{step.position}] {display_names[step.id]} ({step.status})"))
        if step.input_artifact_ref:
            print(field("  input", step.input_artifact_ref))
            print(field("  input_summary", _summarize_artifact(step.input_artifact_ref)))
        if step.output_artifact_ref:
            print(field("  output", step.output_artifact_ref))
            print(field("  output_summary", _summarize_artifact(step.output_artifact_ref)))
        if step.attributes:
            print(field("  attributes", step.attributes))
        if step.error_message:
            print(field("  error", step.error_message))
    print(section("Graph"))
    if not graph.steps:
        print("  (empty)")
    elif filtered_steps and (step_type is not None or step_name is not None or step_status is not None):
        for line in _render_graph(graph, allowed_step_ids=filtered_step_ids):
            print(line)
    else:
        for line in _render_graph(graph):
            print(line)
    try:
        failures = analyze_run(run_id)
    except DetectionError as exc:
        print(f"Detector Note: {exc}")
        failures = list_failures_for_run(run_id)
    if step_type is not None or step_name is not None or step_status is not None:
        failures = [
            failure for failure in failures if failure.step_id is None or failure.step_id in filtered_step_ids
        ]
    print(section("Failures"))
    if not failures:
        print("  (none)")
    else:
        for failure in failures:
            print(bullet(f"[{failure.severity}/{failure.confidence}] {failure.kind}", indent=1))
            print(field("    summary", failure.summary))
            if failure.step_id:
                print(field("    step_id", failure.step_id))
    return 0


def _diff_runs(run_id_1: str, run_id_2: str) -> int:
    try:
        result = diff_runs(run_id_1, run_id_2)
    except DiffError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(section("Summary"))
    print(field("  steps_added", result.summary.added_steps))
    print(field("  steps_removed", result.summary.removed_steps))
    print(field("  steps_modified", result.summary.modified_steps))
    print(field("  steps_unchanged", result.summary.unchanged_steps))
    print(field("  output_changed", "yes" if result.summary.output_changed else "no"))
    if result.summary.key_config_changes:
        print(field("  key_config_changes", ", ".join(result.summary.key_config_changes)))
    if result.topology_changes:
        print(field("  topology_changes", len(result.topology_changes)))

    print(section("Step Diff"))
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

    print(section("Metrics"))
    for metric in result.metrics:
        if metric.delta is None:
            print(f"  {metric.name}: n/a")
            continue
        print(f"  {metric.name}: {_format_metric_delta(metric.name, metric.delta)}")
    return 0


def _replay_run(run_id: str, *, start_at: str | None = None, stop_at: str | None = None) -> int:
    try:
        result = replay_run(run_id, start_at=start_at, stop_at=stop_at)
    except ReplayError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(section("Replay"))
    print(field("Replay", result.run_id))
    print(field("Status", result.status))
    print(field("Replay Window", f"{result.window.start_at or 'run-start'} -> {result.window.stop_at or 'run-end'}"))
    print(field("Simulated Steps", result.simulated_count))
    print(field("Blocked Steps", result.blocked_count))
    print(field("Skipped Steps", result.skipped_count))
    for step in result.step_results:
        print(f"[{step.status}] {step.step_name}")
        print(f"  safety_level: {step.safety_level}")
        print(f"  source: {step.source}")
        print(f"  detail: {step.detail}")
    return 1 if result.blocked_count else 0


def _explain_run(run_id: str, *, failure_kind: str | None = None, severity: str | None = None) -> int:
    try:
        result = explain_run(run_id)
    except ExplainError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(section("Run"))
    print(field("Run", result.run_id))
    failures_by_id = {failure.id: failure for failure in list_failures_for_run(run_id)}
    filtered_explanations = [
        explanation
        for explanation in result.explanations
        if _matches_failure_filter(
            failures_by_id.get(explanation.failure_id),
            failure_kind=failure_kind,
            severity=severity,
        )
    ]
    if not filtered_explanations and (failure_kind or severity):
        print(empty_state(_no_failures_message(failure_kind=failure_kind, severity=severity)))
        return 0
    if not result.explanations:
        print(empty_state("No issues detected."))
        return 0

    steps_by_id = {step.id: step for step in list_steps_for_run(run_id)}
    display_names = _display_name_by_step_id(steps_by_id.values())
    for explanation in filtered_explanations:
        failure = failures_by_id.get(explanation.failure_id)
        print()
        print(field("Failure", explanation.diagnosis))
        if explanation.step_id and explanation.step_id in steps_by_id:
            print(field("Step", display_names[explanation.step_id]))
        elif failure is not None and failure.step_id:
            print(field("Step", failure.step_id))
        print(section("Likely causes"))
        for cause in explanation.likely_causes:
            print(f"- {cause}")
        print(section("Suggestions"))
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


def _render_graph(graph: object, allowed_step_ids: set[str] | None = None) -> list[str]:
    lines: list[str] = []
    visited: set[str] = set()
    step_by_id = {step.id: step for step in graph.steps}
    display_names = _display_name_by_step_id(graph.steps)
    allowed = allowed_step_ids if allowed_step_ids is not None else set(step_by_id)

    def visit(step_id: str, depth: int) -> None:
        if step_id not in allowed:
            return
        if step_id in visited:
            return
        visited.add(step_id)
        node = graph.nodes[step_id]
        step = node.step
        indent = "  " * depth
        relation = "root" if node.parent_step_id is None else f"parent={node.parent_step_id}"
        lines.append(f"{indent}- [{step.position}] {display_names[step.id]} ({relation})")
        for child_step_id in node.child_step_ids:
            visit(child_step_id, depth + 1)

    if allowed_step_ids is None:
        for root_step_id in graph.root_step_ids:
            visit(root_step_id, 1)
    else:
        for step in graph.steps:
            if step.id in allowed:
                visit(step.id, 1)

    orphaned = [step for step in graph.steps if step.id in allowed and step.id not in visited]
    for step in orphaned:
        lines.append(f"  - [{step.position}] {display_names[step.id]} (disconnected)")

    control_flow_edges = [
        edge
        for edge in graph.edges
        if edge.edge_type == EdgeType.CONTROL_FLOW
        and edge.source_step_id in allowed
        and edge.target_step_id in allowed
    ]
    if control_flow_edges:
        lines.append("  Control Flow:")
        for edge in control_flow_edges:
            source = step_by_id[edge.source_step_id]
            target = step_by_id[edge.target_step_id]
            lines.append(
                f"    - [{source.position}] {display_names[source.id]} -> [{target.position}] {display_names[target.id]}"
            )

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


def _filter_steps(
    steps: list[object],
    *,
    step_type: str | None,
    step_name: str | None,
    step_status: str | None,
) -> list[object]:
    filtered = list(steps)
    if step_type is not None:
        filtered = [
            step for step in filtered if _semantic_type_value(step.attributes.get("semantic_type")) == step_type
        ]
    if step_name is not None:
        filtered = [step for step in filtered if step.name == step_name]
    if step_status is not None:
        filtered = [step for step in filtered if step.status == step_status]
    return filtered


def _semantic_type_value(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return SemanticType(value)
    except ValueError:
        return value


def _display_name_by_step_id(steps: object) -> dict[str, str]:
    ordered_steps = sorted(list(steps), key=lambda step: (step.position, step.started_at, step.id))
    counts: dict[tuple[str | None, str], int] = {}
    totals: dict[tuple[str | None, str], int] = {}

    for step in ordered_steps:
        key = (step.parent_step_id, step.name)
        totals[key] = totals.get(key, 0) + 1

    display_names: dict[str, str] = {}
    for step in ordered_steps:
        key = (step.parent_step_id, step.name)
        counts[key] = counts.get(key, 0) + 1
        if totals[key] == 1:
            display_names[step.id] = step.name
        else:
            display_names[step.id] = f"{step.name}#{counts[key]}"
    return display_names


def _matches_failure_filter(
    failure: object,
    *,
    failure_kind: str | None,
    severity: str | None,
) -> bool:
    if failure is None:
        return failure_kind is None and severity is None
    if failure_kind is not None and getattr(failure, "kind", None) != failure_kind:
        return False
    if severity is not None and getattr(failure, "severity", None) != severity:
        return False
    return True


def _no_steps_message(*, step_type: str | None, step_name: str | None, step_status: str | None) -> str:
    filters: list[str] = []
    if step_type is not None:
        filters.append(f"step_type={step_type}")
    if step_name is not None:
        filters.append(f"step_name={step_name}")
    if step_status is not None:
        filters.append(f"step_status={step_status}")
    return f"No steps matched filter: {', '.join(filters)}" if filters else "No steps found."


def _no_failures_message(*, failure_kind: str | None, severity: str | None) -> str:
    filters: list[str] = []
    if failure_kind is not None:
        filters.append(f"kind={failure_kind}")
    if severity is not None:
        filters.append(f"severity={severity}")
    return f"No failures matched filter: {', '.join(filters)}"


if __name__ == "__main__":
    raise SystemExit(main())
