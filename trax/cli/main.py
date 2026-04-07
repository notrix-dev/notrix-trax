"""CLI entrypoint for the Trax foundation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trax.adapters.otel import import_trace
from trax.cli.formatters import bullet, empty_state, field, section, verdict
from trax.cli.theme import (
    style_diff_kind,
    style_empty,
    style_failure_header,
    style_safety_level,
    style_status,
    style_step_name,
    style_verdict,
)
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
    print(verdict(_build_list_verdict(runs)))
    print()
    print(section("Runs"))
    if not runs:
        print(empty_state("No runs found."))
        return 0

    for run in runs:
        print(bullet(run.id))
        print(field("  Name", run.name))
        print(field("  Status", style_status(run.status)))
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

    steps = list_steps_for_run(run_id)
    edges = list_edges_for_run(run_id)
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
    try:
        failures = analyze_run(run_id)
    except DetectionError as exc:
        print(f"Detector Note: {exc}")
        failures = list_failures_for_run(run_id)
    if step_type is not None or step_name is not None or step_status is not None:
        failures = [
            failure for failure in failures if failure.step_id is None or failure.step_id in filtered_step_ids
        ]
    root_segments = len(
        [
            root_step_id
            for root_step_id in graph.root_step_ids
            if step_type is None and step_name is None and step_status is None or root_step_id in filtered_step_ids
        ]
    )
    print(verdict(_build_inspect_verdict(run.status, len(steps), len(failures), root_segments)))
    print()
    print(section("Run"))
    print(field("Run", run.id))
    print(field("Name", run.name))
    print(field("Status", style_status(run.status)))
    print(field("Started", run.started_at))
    print(field("Ended", run.ended_at or "-"))
    if run.artifact_ref:
        print(field("Run Artifact", run.artifact_ref))
        print(field("Run Artifact Summary", _summarize_artifact(run.artifact_ref)))
    if run.error_message:
        print(field("Run Error", run.error_message))
    print(field("Steps", len(steps)))
    print()
    print(section("Step Details"))
    if not filtered_steps:
        print(empty_state(_no_steps_message(step_type=step_type, step_name=step_name, step_status=step_status)))
    for step in filtered_steps:
        print(
            bullet(
                f"[{step.position}] "
                f"{style_step_name(display_names[step.id], _semantic_type_value(step.attributes.get('semantic_type')))} "
                f"({style_status(step.status)})"
            )
        )
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
    print()
    print(style_failure_header("Failures", has_failures=bool(failures)))
    if not failures:
        print(f"  {style_empty('(none)')}")
    else:
        for failure in failures:
            print(
                bullet(
                    f"[{style_status(failure.severity)}/{style_status(failure.confidence)}] "
                    f"{style_status(str(failure.kind))}",
                    indent=1,
                )
            )
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

    print(verdict(_build_diff_verdict(result)))
    print()
    print(section("Summary"))
    print(field("  steps_added", result.summary.added_steps))
    print(field("  steps_removed", result.summary.removed_steps))
    print(field("  steps_modified", result.summary.modified_steps))
    print(field("  steps_unchanged", result.summary.unchanged_steps))
    output_changed = "yes" if result.summary.output_changed else "no"
    print(
        field(
            "  output_changed",
            style_verdict(output_changed, "changed" if result.summary.output_changed else "stable"),
        )
    )
    if result.summary.key_config_changes:
        print(field("  key_config_changes", ", ".join(result.summary.key_config_changes)))
    if result.topology_changes:
        print(field("  topology_changes", len(result.topology_changes)))

    print(section("Step Diff"))
    display_names = _display_name_by_step_diff(result.step_diffs)
    for step_diff in result.step_diffs:
        inline_notes: list[str] = []
        if step_diff.reordered:
            inline_notes.append(f"traversal: {step_diff.before_position} -> {step_diff.after_position}")
        if step_diff.parent_changed:
            inline_notes.append("topology: changed")
        if step_diff.output_missing:
            inline_notes.append("output: missing")
        elif step_diff.output_changed:
            inline_notes.append("output: changed")

        line = (
            f"[{style_diff_kind(step_diff.status)}] "
            f"{style_step_name(display_names[id(step_diff)], step_diff.step_type)}"
        )
        if inline_notes:
            line = f"{line}\t" + ", ".join(inline_notes)
        print(line)
        if step_diff.attribute_changes:
            print("  attrs:")
            for change in step_diff.attribute_changes:
                print(f"    {change.key}: {change.before} -> {change.after}")

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

    print(verdict(_build_replay_verdict(result)))
    print()
    print(section("Replay"))
    print(field("Replay", result.run_id))
    print(field("Status", style_status(result.status)))
    print(field("Replay Window", f"{result.window.start_at or 'run-start'} -> {result.window.stop_at or 'run-end'}"))
    print(field("Simulated Steps", result.simulated_count))
    print(field("Blocked Steps", result.blocked_count))
    print(field("Skipped Steps", result.skipped_count))
    for step in result.step_results:
        print(f"[{style_status(step.status)}] {style_step_name(step.step_name)}")
        print(f"  safety_level: {style_safety_level(step.safety_level)}")
        print(f"  source: {step.source}")
        print(f"  detail: {step.detail}")
    return 1 if result.blocked_count else 0


def _explain_run(run_id: str, *, failure_kind: str | None = None, severity: str | None = None) -> int:
    try:
        result = explain_run(run_id)
    except ExplainError as exc:
        print(str(exc), file=sys.stderr)
        return 1
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
    print(verdict(_build_explain_verdict(filtered_explanations or result.explanations)))
    print()
    print(section("Run"))
    print(field("Run", result.run_id))
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
        print(field("Failure", style_status(str(explanation.diagnosis))))
        if explanation.step_id and explanation.step_id in steps_by_id:
            step = steps_by_id[explanation.step_id]
            print(
                field(
                    "Step",
                    style_step_name(
                        display_names[explanation.step_id],
                        _semantic_type_value(step.attributes.get("semantic_type")),
                    ),
                )
            )
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
    control_flow_targets_by_source: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.edge_type != EdgeType.CONTROL_FLOW:
            continue
        if edge.source_step_id not in allowed or edge.target_step_id not in allowed:
            continue
        control_flow_targets_by_source.setdefault(edge.source_step_id, []).append(edge.target_step_id)
    for source_step_id, target_step_ids in control_flow_targets_by_source.items():
        target_step_ids.sort(key=lambda step_id: step_by_id[step_id].position)

    def visit(step_id: str, depth: int) -> None:
        if step_id not in allowed:
            return
        if step_id in visited:
            return
        visited.add(step_id)
        node = graph.nodes[step_id]
        step = node.step
        indent = "  " * depth
        label = f"{indent}- [{step.position}] {display_names[step.id]}"
        label = f"{indent}- [{step.position}] {style_step_name(display_names[step.id], _semantic_type_value(step.attributes.get('semantic_type')))}"
        if depth == 1 and step.id in graph.root_step_ids:
            label = f"{label} (root)"
        lines.append(label)
        child_step_ids = list(node.child_step_ids)
        if not child_step_ids:
            child_step_ids = control_flow_targets_by_source.get(step_id, [])
        for child_step_id in child_step_ids:
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
        lines.append(
            f"  - [{step.position}] "
            f"{style_step_name(display_names[step.id], _semantic_type_value(step.attributes.get('semantic_type')))} "
            "(disconnected)"
        )

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
                f"    - [{source.position}] {style_step_name(display_names[source.id], _semantic_type_value(source.attributes.get('semantic_type')))} "
                f"-> [{target.position}] {style_step_name(display_names[target.id], _semantic_type_value(target.attributes.get('semantic_type')))}"
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
    return _display_name_map(
        ordered_steps,
        item_id=lambda step: step.id,
        item_name=lambda step: step.name,
        occurrence_key=lambda step: (step.parent_step_id, step.name),
    )


def _display_name_by_step_diff(step_diffs: object) -> dict[int, str]:
    ordered_diffs = list(step_diffs)
    return _display_name_map(
        ordered_diffs,
        item_id=id,
        item_name=lambda step_diff: step_diff.display_name,
        occurrence_key=lambda step_diff: step_diff.display_name,
    )


def _display_name_map(
    items: list[object],
    *,
    item_id: object,
    item_name: object,
    occurrence_key: object,
) -> dict[object, str]:
    counts: dict[object, int] = {}
    totals: dict[object, int] = {}

    for item in items:
        key = occurrence_key(item)
        totals[key] = totals.get(key, 0) + 1

    display_names: dict[object, str] = {}
    for item in items:
        key = occurrence_key(item)
        name = item_name(item)
        counts[key] = counts.get(key, 0) + 1
        if totals[key] == 1:
            display_names[item_id(item)] = name
        else:
            display_names[item_id(item)] = f"{name}#{counts[key]}"
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


def _build_list_verdict(runs: list[object]) -> str:
    if not runs:
        return "no runs found"
    completed = sum(1 for run in runs if getattr(run, "status", None) == "completed")
    failed = sum(1 for run in runs if getattr(run, "status", None) == "failed")
    parts = [f"{len(runs)} runs found"]
    status_parts: list[str] = []
    if completed:
        status_parts.append(f"{completed} completed")
    if failed:
        status_parts.append(f"{failed} failed")
    if status_parts:
        parts.append(", ".join(status_parts))
    return ", ".join(parts)


def _build_inspect_verdict(status: str, step_count: int, failure_count: int, root_segments: int) -> str:
    parts = [f"{status} run", f"{step_count} steps"]
    if failure_count:
        parts.append(f"{failure_count} failures detected")
    else:
        parts.append("no failures")
    if root_segments > 1:
        parts.append(f"graph contains {root_segments} root segments")
    return ", ".join(parts)


def _build_diff_verdict(result: object) -> str:
    parts: list[str] = []
    if getattr(result.summary, "output_changed", False):
        parts.append("output changed")
    added = getattr(result.summary, "added_steps", 0)
    removed = getattr(result.summary, "removed_steps", 0)
    modified = getattr(result.summary, "modified_steps", 0)
    if modified:
        parts.append(f"{modified} steps modified")
    elif added:
        parts.append(f"{added} steps added")
    elif removed:
        parts.append(f"{removed} steps removed")
    if getattr(result, "topology_changes", ()):
        parts.append("topology changed")
    if not parts:
        return "no material change detected"
    return ", ".join(parts)


def _build_explain_verdict(explanations: tuple[object, ...] | list[object]) -> str:
    if not explanations:
        return "no issues detected"
    top = explanations[0]
    diagnosis = str(getattr(top, "diagnosis", "issue")).replace("_", " ")
    noun = "issue" if len(explanations) == 1 else "issues"
    return f"{len(explanations)} {noun} detected, likely caused by {diagnosis}"


def _build_replay_verdict(result: object) -> str:
    if getattr(result, "blocked_count", 0):
        return "replay blocked by unsafe steps"
    if getattr(result, "skipped_count", 0):
        return f"partial replay completed, {getattr(result, 'simulated_count', 0)} steps executed"
    return "replay completed safely"


def _build_graph_verdict(*, step_count: int, edge_count: int, disconnected_segments: int) -> str:
    if step_count == 0:
        return "empty graph"
    if disconnected_segments > 0:
        return f"graph rendered, {disconnected_segments + 1} disconnected segments"
    return f"graph rendered with {step_count} steps and {edge_count} edges"


if __name__ == "__main__":
    raise SystemExit(main())
