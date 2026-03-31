"""Packaging and onboarding smoke tests."""

from __future__ import annotations

from pathlib import Path


def test_readme_contains_quickstart_and_adapter_usage() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Quickstart" in readme
    assert "traced_chat" in readme
    assert "traced_retrieval" in readme
    assert "trax inspect <run_id>" in readme


def test_examples_exist() -> None:
    assert Path("examples/rag-example/app.py").is_file()
    assert Path("examples/agent-example/app.py").is_file()


def test_license_exists() -> None:
    assert Path("LICENSE").is_file()
