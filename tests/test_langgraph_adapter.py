"""LangGraph execution-boundary adapter tests."""

from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from pathlib import Path

from trax.langgraph import traced_invoke, traced_node
from trax.storage import get_run, list_runs, list_steps_for_run


class _GraphState(TypedDict, total=False):
    question: str
    route: str
    docs: list[dict[str, str]]
    answer: str


@traced_node("agent:classify_question", semantic_type="agent")
def _classify_question(state: _GraphState) -> _GraphState:
    return {**state, "route": "retrieval"}


@traced_node(
    "retrieval:query",
    semantic_type="retrieval",
    attributes={"top_k": 2, "backend": "demo_memory"},
)
def _retrieve_context(state: _GraphState) -> _GraphState:
    return {**state, "docs": []}


@traced_node("llm:chat", semantic_type="llm", attributes={"model": "demo-model"})
def _generate_answer(state: _GraphState) -> _GraphState:
    return {**state, "answer": "Trax is a local-first debugger for AI systems."}


@traced_node("agent:finalize_response", semantic_type="agent")
def _finalize_response(state: _GraphState) -> _GraphState:
    return {"answer": state["answer"]}


def _build_graph():
    graph = StateGraph(_GraphState)
    graph.add_node("classify_question", _classify_question)
    graph.add_node("retrieve_context", _retrieve_context)
    graph.add_node("generate_answer", _generate_answer)
    graph.add_node("finalize_response", _finalize_response)
    graph.add_edge(START, "classify_question")
    graph.add_edge("classify_question", "retrieve_context")
    graph.add_edge("retrieve_context", "generate_answer")
    graph.add_edge("generate_answer", "finalize_response")
    graph.add_edge("finalize_response", END)
    return graph.compile()


def test_traced_invoke_captures_real_node_execution_boundaries(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TRAX_HOME", str(tmp_path / ".trax"))

    result = traced_invoke(
        _build_graph(),
        {"question": "What does Trax do?"},
        run_name="langgraph-basic",
    )

    assert result["answer"] == "Trax is a local-first debugger for AI systems."

    runs = list_runs()
    assert len(runs) == 1

    run = get_run(runs[0].id)
    assert run is not None
    assert run.name == "langgraph-basic"

    steps = list_steps_for_run(run.id)
    assert [step.name for step in steps] == [
        "agent:classify_question",
        "retrieval:query",
        "llm:chat",
        "agent:finalize_response",
    ]
    assert steps[0].attributes["semantic_type"] == "agent"
    assert steps[1].attributes["semantic_type"] == "retrieval"
    assert steps[2].attributes["semantic_type"] == "llm"
    assert steps[3].attributes["semantic_type"] == "agent"


def test_traced_invoke_rejects_non_langgraph_objects() -> None:
    with pytest.raises(TypeError, match="CompiledStateGraph"):
        traced_invoke(object(), {"question": "What does Trax do?"})
