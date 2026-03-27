"""Local filesystem and SQLite path configuration for Trax."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = ".trax"
DB_FILE_NAME = "trax.db"
ARTIFACTS_DIR_NAME = "artifacts"
APP_DIR_ENV_VAR = "TRAX_HOME"


def app_dir() -> Path:
    """Return the local Trax application directory."""
    override = os.environ.get(APP_DIR_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / APP_DIR_NAME


def db_path() -> Path:
    """Return the SQLite database path."""
    return app_dir() / DB_FILE_NAME


def artifacts_dir() -> Path:
    """Return the artifact root path."""
    return app_dir() / ARTIFACTS_DIR_NAME
