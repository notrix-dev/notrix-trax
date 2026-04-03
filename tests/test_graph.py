"""Execution graph tests for Trax Feature 2."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from trax.graph import GraphValidationError, build_run_graph
from trax.models import Edge, Step
from trax.sdk import end_run, start_run, trace_step
from trax.storage import list_edges_for_run, list_steps_for_run
from trax.storage.repository import insert_edge


def test_edges_persist_and_graph_reconstructs_for_nested_steps(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("graph-demo")
    root = trace_step("root")
    child_one = trace_step("child-one", parent_step_id=root.id)
    child_two = trace_step("child-two", parent_step_id=root.id)
    end_run()

    steps = list_steps_for_run(run.id)
    edges = list_edges_for_run(run.id)

    assert {step.id for step in steps} == {root.id, child_one.id, child_two.id}
    assert [(edge.source_step_id, edge.target_step_id, edge.edge_type) for edge in edges] == [
        (root.id, child_one.id, "control_flow"),
        (child_one.id, child_two.id, "control_flow"),
    ]

    graph = build_run_graph(run.id, steps, edges)
    assert graph.root_step_ids == (root.id,)
    assert graph.nodes[root.id].child_step_ids == ()
    assert [step.id for step in graph.topological_steps()] == [root.id, child_one.id, child_two.id]


def test_graph_rejects_mixed_run_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run_one = start_run("first")
    step_one = trace_step("one")
    end_run()

    run_two = start_run("second")
    step_two = trace_step("two")
    end_run()

    steps = list_steps_for_run(run_one.id) + list_steps_for_run(run_two.id)
    edges = [
        Edge(
            id=str(uuid.uuid4()),
            run_id=run_one.id,
            source_step_id=step_one.id,
            target_step_id=step_two.id,
            edge_type="control_flow",
        )
    ]

    with pytest.raises(GraphValidationError, match="belongs to run"):
        build_run_graph(run_one.id, steps, edges)


def test_graph_rejects_cycles(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("cycle-demo")
    first = trace_step("first")
    second = trace_step("second")
    end_run()

    insert_edge(
        Edge(
            id=str(uuid.uuid4()),
            run_id=run.id,
            source_step_id=second.id,
            target_step_id=first.id,
            edge_type="control_flow",
        )
    )

    with pytest.raises(GraphValidationError, match="Cycle detected"):
        build_run_graph(run.id, list_steps_for_run(run.id), list_edges_for_run(run.id))


def test_graph_handles_empty_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run = start_run("empty")
    end_run()

    graph = build_run_graph(run.id, list_steps_for_run(run.id), list_edges_for_run(run.id))
    assert graph.root_step_ids == ()
    assert graph.topological_steps() == []
