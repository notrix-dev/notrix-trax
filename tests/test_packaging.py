"""Packaging and onboarding smoke tests."""

from __future__ import annotations

from pathlib import Path


def test_readme_contains_quickstart_and_adapter_usage() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Quickstart" in readme
    assert "traced_chat" in readme
    assert "traced_retrieval" in readme
    assert "traced_invoke" in readme
    assert "Invocation-level and node-level tracing" in readme
    assert "trax inspect <run_id>" in readme


def test_examples_exist() -> None:
    assert Path("examples/basic_capture.py").is_file()
    assert Path("examples/rag_failure/app.py").is_file()
    assert Path("examples/agent_loop/app.py").is_file()
    assert Path("examples/langgraph_basic.py").is_file()


def test_license_exists() -> None:
    assert Path("LICENSE").is_file()
