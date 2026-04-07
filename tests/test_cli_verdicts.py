from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from trax.models import Edge, Failure, Run, Step
from trax.storage import bootstrap_local_storage
from trax.storage.artifacts import write_artifact
from trax.storage.repository import insert_edge, insert_run, insert_step, replace_failures_for_run


def test_list_and_graph_emit_verdicts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))
    run = _persist_run("graph-verdict", steps=[_step("prepare", 1, {"ok": True})], edges=[])

    listed = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "list"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )
    graphed = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "graph", "--run-id", run.id, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert listed.returncode == 0
    assert "Verdict: 1 runs found" in listed.stdout
    assert graphed.returncode == 0
    assert graphed.stderr == ""


def test_inspect_diff_replay_and_explain_emit_verdicts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    inspect_run = _persist_run("inspect-verdict", steps=[_step("prepare", 1, {"ok": True})], edges=[])
    before = _persist_run("before", steps=[_step("prepare", 1, {"ok": True})], edges=[])
    after = _persist_run("after", steps=[_step("prepare", 1, {"ok": False})], edges=[])
    replay_run = _persist_run(
        "replay-verdict",
        steps=[_step("prepare", 1, {"ok": True}, safety_level="safe_read")],
        edges=[],
    )
    explain_run = _persist_run("explain-verdict", steps=[_step("retrieve", 1, {"docs": []})], edges=[])
    replace_failures_for_run(
        explain_run.id,
        [
            Failure(
                id=str(uuid.uuid4()),
                run_id=explain_run.id,
                step_id=None,
                kind="empty_retrieval",
                severity="medium",
                confidence="high",
                summary="Retrieval returned no docs.",
                evidence={},
            )
        ],
    )

    inspected = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "inspect", inspect_run.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )
    diffed = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "diff", before.id, after.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )
    replayed = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "replay", replay_run.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )
    explained = subprocess.run(
        [sys.executable, "-m", "trax.cli.main", "explain", explain_run.id],
        capture_output=True,
        text=True,
        check=False,
        env={"TRAX_HOME": str(tmp_path / ".trax")},
    )

    assert inspected.stdout.splitlines()[0].startswith("Verdict:")
    assert "Verdict: completed run, 1 steps" in inspected.stdout
    assert "Verdict: output changed" in diffed.stdout
    assert replayed.stdout.splitlines()[0].startswith("Verdict:")
    assert "Verdict: replay completed safely" in replayed.stdout
    assert explained.stdout.splitlines()[0].startswith("Verdict:")
    assert "Verdict: 1 issue detected" in explained.stdout


def _persist_run(name: str, *, steps: list[dict[str, object]], edges: list[tuple[str, int, int]]) -> Run:
    bootstrap_local_storage()
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        name=name,
        status="completed",
        started_at="2026-04-06T10:00:00+00:00",
        ended_at="2026-04-06T10:00:01+00:00",
        artifact_ref=write_artifact(run_id, "run-output", {"result": "ok"}),
    )
    insert_run(run)

    persisted_steps: list[Step] = []
    for raw_step in steps:
        step = Step(
            id=str(uuid.uuid4()),
            run_id=run_id,
            name=str(raw_step["name"]),
            status="completed",
            position=int(raw_step["position"]),
            started_at="2026-04-06T10:00:00+00:00",
            ended_at="2026-04-06T10:00:01+00:00",
            safety_level=str(raw_step.get("safety_level", "unknown")),
            output_artifact_ref=write_artifact(run_id, f"step-{raw_step['position']}-output", raw_step["output_payload"]),
            attributes={},
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


def _step(name: str, position: int, output_payload: dict[str, object], *, safety_level: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": name,
        "position": position,
        "output_payload": output_payload,
    }
    if safety_level is not None:
        payload["safety_level"] = safety_level
    return payload
