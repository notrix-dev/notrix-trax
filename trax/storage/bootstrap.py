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
        connection.commit()
