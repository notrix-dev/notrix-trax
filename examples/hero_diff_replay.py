"""Create two comparable runs for the diff / explain / replay quickstart."""

from __future__ import annotations

from trax import run, step

QUESTION = "Explain Kubernetes in one sentence."


def search_docs(query: str, variant: str) -> list[dict[str, str]]:
    if variant == "baseline":
        return [
            {
                "id": "doc-1",
                "text": "Kubernetes is an orchestration system for containerized applications.",
            },
            {
                "id": "doc-2",
                "text": "It automates deployment, scaling, and management of containers.",
            },
        ]
    return []


def generate_answer(question: str, docs: list[dict[str, str]]) -> str:
    if not docs:
        return "Kubernetes is a platform related to containers."
    combined = " ".join(doc["text"] for doc in docs)
    if "orchestration system" in combined:
        return "Kubernetes automates deployment and management of containerized applications."
    return "Kubernetes is a powerful cloud-native platform for containers."


def run_pipeline(name: str, retrieval_variant: str, *, temperature: float, top_k: int) -> str:
    with run(name, input={"question": QUESTION}) as current_run:
        with step(
            "retrieve_docs",
            input={"query": QUESTION},
            attributes={
                "semantic_type": "retrieval",
                "backend": "demo_search",
                "top_k": top_k,
                "safety_level": "safe_read",
            },
        ) as retrieval_step:
            docs = search_docs(QUESTION, retrieval_variant)
            retrieval_step.output = {"docs": docs}

        with step(
            "generate_answer",
            input={"question": QUESTION, "docs": docs},
            attributes={
                "semantic_type": "llm",
                "model": "demo-model",
                "temperature": temperature,
                "safety_level": "safe_read",
            },
        ) as llm_step:
            answer = generate_answer(QUESTION, docs)
            llm_step.output = {"answer": answer}

    return current_run.id


def main() -> None:
    run_a = run_pipeline("quickstart-baseline", "baseline", temperature=0.2, top_k=2)
    run_b = run_pipeline("quickstart-changed", "changed", temperature=0.9, top_k=1)

    print("Created runs:")
    print(f"  baseline: {run_a}")
    print(f"  changed:  {run_b}")
    print()
    print("Now try:")
    print("  trax list")
    print(f"  trax diff {run_a} {run_b}")
    print(f"  trax explain {run_b}")
    print(f"  trax replay {run_b}")


if __name__ == "__main__":
    main()
