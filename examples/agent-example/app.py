"""Minimal multi-step agent-style Trax example."""

from __future__ import annotations

from trax.sdk import end_run, start_run, trace_step


def main() -> None:
    run = start_run("agent-example", input_payload={"task": "answer a question"})
    trace_step(
        "reasoning",
        input_payload={"goal": "plan answer"},
        output_payload={"plan": "retrieve then answer"},
        attributes={"semantic_type": "reasoning", "safety_level": "safe_read"},
    )
    trace_step(
        "retrieval:knowledge_base",
        input_payload={"query": "Trax"},
        output_payload={"docs": []},
        attributes={"semantic_type": "retrieval", "top_k": 1, "safety_level": "safe_read"},
    )
    trace_step(
        "generation",
        input_payload={"draft": "fallback answer"},
        output_payload={"answer": "Trax helps debug AI systems."},
        attributes={"semantic_type": "llm", "safety_level": "safe_read"},
    )
    end_run(output_payload={"run_id": run.id, "status": "completed"})
    print(run.id)


if __name__ == "__main__":
    main()
