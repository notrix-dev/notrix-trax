"""SQLite repositories for minimal run, step, and edge persistence."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from trax.config import db_path
from trax.models import Edge, Run, Step


def insert_run(run: Run) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO runs (id, name, status, started_at, ended_at, artifact_ref, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.id,
                run.name,
                run.status,
                run.started_at,
                run.ended_at,
                run.artifact_ref,
                run.error_message,
            ),
        )
        connection.commit()


def update_run_completion(
    run_id: str,
    status: str,
    ended_at: str,
    artifact_ref: str | None = None,
    error_message: str | None = None,
) -> None:
    with _connect() as connection:
        connection.execute(
            """
            UPDATE runs
            SET status = ?, ended_at = ?, artifact_ref = ?, error_message = ?
            WHERE id = ?
            """,
            (status, ended_at, artifact_ref, error_message, run_id),
        )
        connection.commit()


def insert_step(step: Step) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO steps (
                id, run_id, name, status, position, started_at, ended_at, parent_step_id,
                input_artifact_ref, output_artifact_ref, attributes_json, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step.id,
                step.run_id,
                step.name,
                step.status,
                step.position,
                step.started_at,
                step.ended_at,
                step.parent_step_id,
                step.input_artifact_ref,
                step.output_artifact_ref,
                json.dumps(step.attributes, sort_keys=True),
                step.error_message,
            ),
        )
        connection.commit()


def insert_edge(edge: Edge) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO edges (id, run_id, source_step_id, target_step_id, edge_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                edge.id,
                edge.run_id,
                edge.source_step_id,
                edge.target_step_id,
                edge.edge_type,
            ),
        )
        connection.commit()


def get_run(run_id: str) -> Run | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, name, status, started_at, ended_at, artifact_ref, error_message
            FROM runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

    if row is None:
        return None

    return Run(
        id=row["id"],
        name=row["name"],
        status=row["status"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        artifact_ref=row["artifact_ref"],
        error_message=row["error_message"],
    )


def list_steps_for_run(run_id: str) -> list[Step]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, run_id, name, status, position, started_at, ended_at, parent_step_id,
                   input_artifact_ref, output_artifact_ref, attributes_json, error_message
            FROM steps
            WHERE run_id = ?
            ORDER BY position ASC, started_at ASC
            """,
            (run_id,),
        ).fetchall()

    return [
        Step(
            id=row["id"],
            run_id=row["run_id"],
            name=row["name"],
            status=row["status"],
            position=row["position"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            parent_step_id=row["parent_step_id"],
            input_artifact_ref=row["input_artifact_ref"],
            output_artifact_ref=row["output_artifact_ref"],
            attributes=json.loads(row["attributes_json"] or "{}"),
            error_message=row["error_message"],
        )
        for row in rows
    ]


def list_edges_for_run(run_id: str) -> list[Edge]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, run_id, source_step_id, target_step_id, edge_type
            FROM edges
            WHERE run_id = ?
            ORDER BY rowid ASC
            """,
            (run_id,),
        ).fetchall()

    return [
        Edge(
            id=row["id"],
            run_id=row["run_id"],
            source_step_id=row["source_step_id"],
            target_step_id=row["target_step_id"],
            edge_type=row["edge_type"],
        )
        for row in rows
    ]


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(db_path())
    connection.row_factory = sqlite3.Row
    return connection
