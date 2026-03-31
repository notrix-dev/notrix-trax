"""Idempotent local storage bootstrap for Trax."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from trax.config import app_dir, artifacts_dir, db_path


@dataclass(frozen=True)
class BootstrapResult:
    app_dir: Path
    db_path: Path
    artifacts_dir: Path


def bootstrap_local_storage() -> BootstrapResult:
    """Create required local directories and initialize SQLite."""
    app_root = app_dir()
    artifact_root = artifacts_dir()
    database_path = db_path()

    app_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    _initialize_sqlite(database_path)

    return BootstrapResult(
        app_dir=app_root,
        db_path=database_path,
        artifacts_dir=artifact_root,
    )


def _initialize_sqlite(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 1;")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                artifact_ref TEXT,
                error_message TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS steps (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                position INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                safety_level TEXT NOT NULL DEFAULT 'unknown',
                parent_step_id TEXT,
                input_artifact_ref TEXT,
                output_artifact_ref TEXT,
                attributes_json TEXT,
                error_message TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(id),
                FOREIGN KEY (parent_step_id) REFERENCES steps(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                source_step_id TEXT NOT NULL,
                target_step_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id),
                FOREIGN KEY (source_step_id) REFERENCES steps(id),
                FOREIGN KEY (target_step_id) REFERENCES steps(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS failures (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_id TEXT,
                kind TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence TEXT NOT NULL,
                summary TEXT NOT NULL,
                evidence_json TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(id),
                FOREIGN KEY (step_id) REFERENCES steps(id)
            )
            """
        )
        existing_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(steps)").fetchall()
        }
        if "parent_step_id" not in existing_columns:
            connection.execute("ALTER TABLE steps ADD COLUMN parent_step_id TEXT")
        if "safety_level" not in existing_columns:
            connection.execute("ALTER TABLE steps ADD COLUMN safety_level TEXT NOT NULL DEFAULT 'unknown'")
        connection.commit()
