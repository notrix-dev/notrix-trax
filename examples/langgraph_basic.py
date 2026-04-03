"""Real LangGraph compiled-graph example for Trax."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from trax.langgraph import traced_invoke, traced_node


class GraphState(TypedDict, total=False):
    question: str
    route: str
    docs: list[dict[str, str]]
    answer: str


@traced_node("agent:classify_question", semantic_type="agent")
def classify_question(state: GraphState) -> GraphState:
    question = str(state["question"])
    route = "retrieval" if "trax" in question.lower() else "direct"
    return {**state, "route": route}


@traced_node("retrieval:query", semantic_type="retrieval", attributes={"top_k": 2, "backend": "demo_memory"})
def retrieve_context(state: GraphState) -> GraphState:
    docs: list[dict[str, str]] = []
    return {**state, "docs": docs}


@traced_node("llm:chat", semantic_type="llm", attributes={"model": "demo-model"})
def generate_answer(state: GraphState) -> GraphState:
    docs = state.get("docs") or []
    if docs:
        answer = "Trax captures, diffs, replays, and explains agent runs."
    else:
        answer = "Trax is a local-first debugger for AI systems."
    return {**state, "answer": answer}


@traced_node("agent:finalize_response", semantic_type="agent")
def finalize_response(state: GraphState) -> GraphState:
    return {"answer": state["answer"]}


def build_graph() -> Any:
    graph = StateGraph(GraphState)
    graph.add_node("classify_question", classify_question)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("finalize_response", finalize_response)
    graph.add_edge(START, "classify_question")
    graph.add_edge("classify_question", "retrieve_context")
    graph.add_edge("retrieve_context", "generate_answer")
    graph.add_edge("generate_answer", "finalize_response")
    graph.add_edge("finalize_response", END)
    return graph.compile()


def main() -> None:
    graph = build_graph()
    result = traced_invoke(graph, {"question": "What does Trax do?"}, run_name="langgraph-basic")
    print(result["answer"])


if __name__ == "__main__":
    main()
