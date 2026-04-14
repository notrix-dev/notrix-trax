"""Create two deterministic runs showing generation drift from prompt/config changes."""

from __future__ import annotations

from trax import run, step

QUESTION = "Explain Kubernetes in one sentence."
DOCS = [
    {
        "id": "doc-1",
        "text": "Kubernetes is an orchestration system for containerized applications.",
    },
    {
        "id": "doc-2",
        "text": "It automates deployment, scaling, and management of containers.",
    },
]


def search_docs(query: str, top_k: int) -> list[dict[str, str]]:
    del query
    return DOCS[:top_k]


def prepare_prompt(*, prompt_style: str, temperature: float) -> dict[str, object]:
    definition_first = "definition-first" in prompt_style.lower()
    avoid_jargon = "avoid jargon" in prompt_style.lower() or "high-level" in prompt_style.lower()
    focus_on_platform = "platform" in prompt_style.lower() or "cloud-native" in prompt_style.lower()
    return {
        "prompt_style": prompt_style,
        "definition_first": definition_first,
        "avoid_jargon": avoid_jargon,
        "focus_on_platform": focus_on_platform,
        "temperature": temperature,
    }


def extract_capabilities(docs: list[dict[str, str]]) -> dict[str, str]:
    combined = " ".join(doc["text"] for doc in docs).lower()
    return {
        "has_definition": "orchestration system" in combined,
        "has_automation": "automates deployment" in combined,
        "definition_phrase": "an orchestration system for containerized applications",
        "automation_phrase": "that automates deployment, scaling, and management",
        "generic_phrase": "a platform for running and managing containers",
    }


def generate_answer(question: str, docs: list[dict[str, str]], *, prompt_config: dict[str, object]) -> str:
    del question
    capabilities = extract_capabilities(docs)
    definition_first = bool(prompt_config["definition_first"])
    avoid_jargon = bool(prompt_config["avoid_jargon"])
    focus_on_platform = bool(prompt_config["focus_on_platform"])
    temperature = float(prompt_config["temperature"])

    if definition_first and not avoid_jargon and temperature <= 0.3 and capabilities["has_definition"]:
        answer = f"Kubernetes is {capabilities['definition_phrase']}"
        if capabilities["has_automation"]:
            answer += f" {capabilities['automation_phrase']}."
        else:
            answer += "."
        return answer

    if focus_on_platform or avoid_jargon or temperature >= 0.7:
        return f"Kubernetes is {capabilities['generic_phrase']}."

    answer = f"Kubernetes is {capabilities['definition_phrase']}."
    return answer


def run_pipeline(name: str, *, prompt_style: str, temperature: float, top_k: int) -> str:
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
            docs = search_docs(QUESTION, top_k)
            retrieval_step.output = {"docs": docs}

        with step(
            "prepare_prompt",
            input={"question": QUESTION, "style": prompt_style},
            attributes={"semantic_type": "transform", "safety_level": "safe_read"},
        ) as prompt_step:
            prompt_config = prepare_prompt(prompt_style=prompt_style, temperature=temperature)
            prompt = f"{prompt_style}\nQuestion: {QUESTION}"
            prompt_step.output = {"prompt": prompt, "config": prompt_config}

        with step(
            "generate_answer",
            input={"prompt": prompt, "config": prompt_config, "docs": docs},
            attributes={
                "semantic_type": "llm",
                "model": "demo-model",
                "temperature": temperature,
                "safety_level": "safe_read",
            },
        ) as llm_step:
            answer = generate_answer(QUESTION, docs, prompt_config=prompt_config)
            llm_step.output = {"answer": answer}

        current_run.output = {
            "answer": answer,
            "docs_found": len(docs),
            "prompt_style": prompt_style,
            "temperature": temperature,
        }

    return current_run.id


def main() -> None:
    run_a = run_pipeline(
        "quickstart-baseline",
        prompt_style="Be precise and definition-first.",
        temperature=0.4,
        top_k=2,
    )
    run_b = run_pipeline(
        "quickstart-changed",
        prompt_style="Be high-level, audience-friendly, and avoid jargon. Describe it as a platform.",
        temperature=0.2,
        top_k=2,
    )

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
