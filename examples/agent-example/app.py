"""Minimal multi-step agent-style Trax example."""

from __future__ import annotations

from trax import run, step, traced_step


@traced_step("reasoning", attributes={"semantic_type": "reasoning", "safety_level": "safe_read"})
def build_plan(task: str) -> dict[str, str]:
    return {"plan": f"retrieve then answer: {task}"}


def main() -> None:
    with run("agent-example", input={"task": "answer a question"}) as current_run:
        build_plan("answer a question")
        with step(
            "retrieval:knowledge_base",
            input={"query": "Trax"},
            attributes={"semantic_type": "retrieval", "top_k": 1, "safety_level": "safe_read"},
            output={"docs": []},
        ):
            pass
        with step(
            "generation",
            input={"draft": "fallback answer"},
            attributes={"semantic_type": "llm", "safety_level": "safe_read"},
            output={"answer": "Trax helps debug AI systems."},
        ):
            pass
    print(current_run.id)


if __name__ == "__main__":
    main()
