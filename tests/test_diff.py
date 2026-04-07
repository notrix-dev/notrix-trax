"""Diff engine tests for Trax Feature 3."""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from trax.diff import diff_runs
from trax.models import Edge, Run, Step
from trax.storage import bootstrap_local_storage
from trax.storage.artifacts import write_artifact
from trax.storage.repository import insert_edge, insert_run, insert_step


def test_diff_identical_runs_produces_no_changes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run_one = _persist_run(
        "run-one",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:01+00:00",
        output_payload={"tokens": 100, "cost": 0.1, "answer": "ok"},
        steps=[
            _step("prep", 1, attributes={"semantic_type": "transform"}, output_payload={"value": "x"}),
            _step("llm:answer_generation", 2, attributes={"semantic_type": "llm"}, output_payload={"answer": "ok"}),
        ],
        edges=[("control_flow", 0, 1)],
    )
    run_two = _persist_run(
        "run-two",
        started_at="2026-03-30T10:01:00+00:00",
        ended_at="2026-03-30T10:01:01+00:00",
        output_payload={"tokens": 100, "cost": 0.1, "answer": "ok"},
        steps=[
            _step("prep", 1, attributes={"semantic_type": "transform"}, output_payload={"value": "x"}),
            _step("llm:answer_generation", 2, attributes={"semantic_type": "llm"}, output_payload={"answer": "ok"}),
        ],
        edges=[("control_flow", 0, 1)],
    )

    result = diff_runs(run_one.id, run_two.id)

    assert result.summary.added_steps == 0
    assert result.summary.removed_steps == 0
    assert result.summary.modified_steps == 0
    assert result.summary.unchanged_steps == 2
    assert result.summary.output_changed is False


def test_diff_detects_added_removed_modified_and_metrics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    run_one = _persist_run(
        "before",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:01+00:00",
        output_payload={"tokens": 100, "cost": 0.10, "answer": "ok"},
        steps=[
            _step("retrieval:faq_search", 1, attributes={"semantic_type": "retrieval", "top_k": 3}, output_payload={"docs": [1, 2, 3]}),
            _step("llm:answer_generation", 2, attributes={"semantic_type": "llm", "model": "gpt-a"}, output_payload={"answer": "old"}),
        ],
        edges=[("control_flow", 0, 1)],
    )
    run_two = _persist_run(
        "after",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:03+00:00",
        output_payload={"tokens": 130, "cost": 0.12, "answer": "new"},
        steps=[
            _step("retrieval:faq_search", 1, attributes={"semantic_type": "retrieval", "top_k": 5}, output_payload={"docs": [1, 2, 3, 4, 5]}),
            _step("reranker:cross_encoder", 2, attributes={"semantic_type": "rerank"}, output_payload={"docs": [5, 4]}),
            _step("llm:answer_generation", 3, attributes={"semantic_type": "llm", "model": "gpt-a"}, output_payload={"answer": "new"}),
        ],
        edges=[("control_flow", 0, 1), ("control_flow", 1, 2)],
    )

    result = diff_runs(run_one.id, run_two.id)

    assert result.summary.added_steps == 1
    assert result.summary.removed_steps == 0
    assert result.summary.modified_steps == 2
    assert result.summary.output_changed is True
    assert result.summary.key_config_changes == ("top_k",)
    assert any(step_diff.status == "ADDED" and step_diff.display_name == "reranker:cross_encoder" for step_diff in result.step_diffs)
    assert any(step_diff.status == "MODIFIED" and step_diff.display_name == "retrieval:faq_search" for step_diff in result.step_diffs)
    metrics = {metric.name: metric for metric in result.metrics}
    assert metrics["latency_ms"].delta == 2000
    assert metrics["tokens"].delta == 30
    assert metrics["cost"].delta == 0.01999999999999999


def test_diff_cli_renders_readable_sections(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    before = _persist_run(
        "cli-before",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:01+00:00",
        output_payload={"answer": "old"},
        steps=[
            _step("retrieval:faq_search", 1, attributes={"semantic_type": "retrieval", "top_k": 3}, output_payload={"docs": [1]}),
        ],
        edges=[],
    )
    after = _persist_run(
        "cli-after",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:02+00:00",
        output_payload={"answer": "new"},
        steps=[
            _step("retrieval:faq_search", 1, attributes={"semantic_type": "retrieval", "top_k": 5}, output_payload={"docs": [1, 2]}),
        ],
        edges=[],
    )

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "diff", before.id, after.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert "── Impact Summary ──" in result.stdout
    assert "Output: CHANGED" in result.stdout
    assert "Topology: UNCHANGED" in result.stdout
    assert "Steps: 0 added, 1 modified, 0 removed, 0 unchanged" in result.stdout
    assert "── Step Diff (Execution Order) ──" in result.stdout
    assert "── Metrics ──" in result.stdout
    assert "[MODIFIED] retrieval:faq_search" in result.stdout
    assert "(output: changed)" in result.stdout
    assert "top_k: 3 -> 5" in result.stdout


def test_diff_cli_disambiguates_repeated_step_names_with_suffixes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    before = _persist_run(
        "loop-before",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:01+00:00",
        output_payload={"answer": "old"},
        steps=[
            _step("transform:rewrite_query", 1, attributes={"semantic_type": "transform"}, output_payload={"query": "one"}),
            _step("retrieval:knowledge_lookup", 2, attributes={"semantic_type": "retrieval"}, output_payload={"docs": ["a"]}),
            _step("llm:final_answer", 3, attributes={"semantic_type": "llm"}, output_payload={"answer": "old"}),
        ],
        edges=[("control_flow", 0, 1), ("control_flow", 1, 2)],
    )
    after = _persist_run(
        "loop-after",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:02+00:00",
        output_payload={"answer": "new"},
        steps=[
            _step("transform:rewrite_query", 1, attributes={"semantic_type": "transform"}, output_payload={"query": "one"}),
            _step("retrieval:knowledge_lookup", 2, attributes={"semantic_type": "retrieval"}, output_payload={"docs": ["a"]}),
            _step("transform:rewrite_query", 3, attributes={"semantic_type": "transform"}, output_payload={"query": "two"}),
            _step("retrieval:knowledge_lookup", 4, attributes={"semantic_type": "retrieval"}, output_payload={"docs": ["b"]}),
            _step("llm:final_answer", 5, attributes={"semantic_type": "llm"}, output_payload={"answer": "new"}),
        ],
        edges=[("control_flow", 0, 1), ("control_flow", 1, 2), ("control_flow", 2, 3), ("control_flow", 3, 4)],
    )

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "diff", before.id, after.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert "transform:rewrite_query#1" in result.stdout
    assert "transform:rewrite_query#2" in result.stdout
    assert "retrieval:knowledge_lookup#1" in result.stdout
    assert "retrieval:knowledge_lookup#2" in result.stdout


def test_diff_cli_renders_traversal_and_output_inline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    before = _persist_run(
        "inline-before",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:01+00:00",
        output_payload={"answer": "old"},
        steps=[
            _step("transform:rewrite_query", 1, attributes={"semantic_type": "transform"}, output_payload={"query": "one"}),
            _step("llm:final_answer", 2, attributes={"semantic_type": "llm"}, output_payload={"answer": "old"}),
        ],
        edges=[("control_flow", 0, 1)],
    )
    after = _persist_run(
        "inline-after",
        started_at="2026-03-30T10:00:00+00:00",
        ended_at="2026-03-30T10:00:02+00:00",
        output_payload={"answer": "new"},
        steps=[
            _step("transform:rewrite_query", 1, attributes={"semantic_type": "transform"}, output_payload={"query": "one"}),
            _step("reasoning:assess_progress", 2, attributes={"semantic_type": "reasoning"}, output_payload={"retry": True}),
            _step("llm:final_answer", 3, attributes={"semantic_type": "llm"}, output_payload={"answer": "new"}),
        ],
        edges=[("control_flow", 0, 1), ("control_flow", 1, 2)],
    )

    result = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "diff", before.id, after.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert result.returncode == 0
    assert "[MODIFIED] llm:final_answer" in result.stdout
    assert "(traversal: 2 -> 3, output: changed)" in result.stdout


def _persist_run(
    name: str,
    *,
    started_at: str,
    ended_at: str,
    output_payload: dict[str, object],
    steps: list[dict[str, object]],
    edges: list[tuple[str, int, int]],
) -> Run:
    bootstrap_local_storage()
    run_id = str(uuid.uuid4())
    artifact_ref = write_artifact(run_id, "run-output", output_payload)
    run = Run(
        id=run_id,
        name=name,
        status="completed",
        started_at=started_at,
        ended_at=ended_at,
        artifact_ref=artifact_ref,
    )
    insert_run(run)

    persisted_steps: list[Step] = []
    for raw_step in steps:
        step_id = str(uuid.uuid4())
        output_ref = write_artifact(run_id, f"step-{raw_step['position']}-output", raw_step["output_payload"])
        step = Step(
            id=step_id,
            run_id=run_id,
            name=str(raw_step["name"]),
            status="completed",
            position=int(raw_step["position"]),
            started_at=started_at,
            ended_at=ended_at,
            parent_step_id=raw_step.get("parent_step_id"),
            output_artifact_ref=output_ref,
            attributes=dict(raw_step["attributes"]),
        )
        insert_step(step)
        persisted_steps.append(step)

    for edge_type, source_index, target_index in edges:
        insert_edge(
            Edge(
                id=str(uuid.uuid4()),
                run_id=run_id,
                source_step_id=persisted_steps[source_index].id,
                target_step_id=persisted_steps[target_index].id,
                edge_type=edge_type,
            )
        )
    return run


def _step(name: str, position: int, *, attributes: dict[str, object], output_payload: dict[str, object], parent_step_id: str | None = None) -> dict[str, object]:
    return {
        "name": name,
        "position": position,
        "attributes": attributes,
        "output_payload": output_payload,
        "parent_step_id": parent_step_id,
    }
