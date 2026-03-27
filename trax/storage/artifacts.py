"""Filesystem-backed artifact helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trax.config import artifacts_dir


def write_artifact(run_id: str, artifact_name: str, payload: Any) -> str | None:
    """Persist a JSON artifact and return its relative reference."""
    if payload is None:
        return None

    run_artifact_dir = artifacts_dir() / run_id
    run_artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_artifact_dir / f"{artifact_name}.json"

    with artifact_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)

    return str(Path(run_id) / artifact_path.name)


def read_artifact(artifact_ref: str) -> Any:
    """Read a JSON artifact by relative reference."""
    artifact_path = artifacts_dir() / artifact_ref
    with artifact_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
