"""Deterministic agent example showing a bounded retry loop."""

from __future__ import annotations

import re

from trax import run, step

QUESTION = "What does Trax do?"
MAX_ATTEMPTS = 2
CORPUS = [
    {
        "id": "doc-1",
        "title": "Trax debugger",
        "text": "Trax captures AI runs, diffs execution graphs, and replays safely.",
    },
    {
        "id": "doc-2",
        "title": "Explain capability",
        "text": "Trax explains failures using local evidence.",
    },
    {
        "id": "doc-3",
        "title": "General tracing",
        "text": "Tracing tools record steps, artifacts, and workflow metadata.",
    },
]


def rewrite_query(question: str, attempt: int, *, precise_first_query: bool) -> str:
    del question
    if precise_first_query and attempt == 1:
        return "Trax AI runs diff replay explain failures"
    if attempt == 1:
        return "trace workflow metadata"
    return "trace workflow metadata steps artifacts"


def retrieve_docs(query: str) -> list[dict[str, str]]:
    query_terms = set(query.lower().split())
    scored_docs = []
    for doc in CORPUS:
        text_terms = set(f"{doc['title']} {doc['text']}".lower().split())
        score = len(query_terms & text_terms)
        scored_docs.append((score, doc))
    ranked = [doc for score, doc in sorted(scored_docs, key=lambda item: (-item[0], item[1]["id"])) if score > 0]
    return [{"id": doc["id"], "text": doc["text"]} for doc in ranked[:2]]


def extract_facts(docs: list[dict[str, str]]) -> list[str]:
    facts: list[str] = []
    seen: set[str] = set()
    for doc in docs:
        text = doc["text"].replace(".", "")
        text = text.replace(" and ", ", ")
        parts = [part.strip() for part in text.split(",") if part.strip()]
        for part in parts:
            cleaned = re.sub(r"^Trax\s+", "", part).strip()
            if cleaned:
                cleaned = cleaned[0].lower() + cleaned[1:]
            if cleaned and cleaned not in seen:
                facts.append(cleaned)
                seen.add(cleaned)
    return facts


def join_facts(facts: list[str]) -> str:
    if not facts:
        return "works from the available local evidence"
    if len(facts) == 1:
        return facts[0]
    if len(facts) == 2:
        return f"{facts[0]} and {facts[1]}"
    return f"{', '.join(facts[:-1])}, and {facts[-1]}"


def draft_answer(docs: list[dict[str, str]]) -> str:
    return f"Trax {join_facts(extract_facts(docs)[:3])}."


def validate_answer(answer: str) -> dict[str, object]:
    missing = []
    lowered = answer.lower()
    if "captures ai runs" not in lowered:
        missing.append("captures ai runs")
    if "explains failures" not in lowered:
        missing.append("explains failures")
    return {"revision_required": bool(missing), "missing_concepts": missing}


def assess_progress(previous_docs: list[dict[str, str]], current_docs: list[dict[str, str]], attempt: int) -> dict[str, object]:
    previous_ids = [doc["id"] for doc in previous_docs]
    current_ids = [doc["id"] for doc in current_docs]
    same_evidence = previous_ids == current_ids
    stop = same_evidence or attempt >= MAX_ATTEMPTS
    reason = "no_meaningful_progress" if same_evidence else "max_attempts_reached"
    return {"stop_retry": stop, "reason": reason, "same_evidence": same_evidence}


def run_agent(name: str, *, precise_first_query: bool) -> str:
    with run(name, input={"task": QUESTION}) as current_run:
        with step(
            "plan_task",
            input={"task": QUESTION},
            attributes={"semantic_type": "reasoning", "safety_level": "safe_read"},
        ) as planning_step:
            planning_step.output = {"plan": "retrieve, draft, validate, and retry if incomplete"}

        previous_docs: list[dict[str, str]] = []
        final_answer = ""
        validation: dict[str, object] = {"revision_required": False, "missing_concepts": []}

        for attempt in range(1, MAX_ATTEMPTS + 1):
            with step(
                "rewrite_query",
                input={"question": QUESTION, "attempt": attempt},
                attributes={"semantic_type": "transform", "safety_level": "safe_read"},
            ) as query_step:
                retrieval_query = rewrite_query(QUESTION, attempt, precise_first_query=precise_first_query)
                query_step.output = {"query": retrieval_query, "attempt": attempt}

            with step(
                "knowledge_lookup",
                input={"query": retrieval_query, "attempt": attempt},
                attributes={"semantic_type": "retrieval", "top_k": 2, "safety_level": "safe_read"},
            ) as retrieval_step:
                docs = retrieve_docs(retrieval_query)
                retrieval_step.output = {"docs": docs, "attempt": attempt}

            with step(
                "draft_answer",
                input={"docs": docs, "attempt": attempt},
                attributes={"semantic_type": "llm", "model": "demo-model", "safety_level": "safe_read"},
            ) as draft_step:
                draft = draft_answer(docs)
                draft_step.output = {"draft": draft, "attempt": attempt}

            with step(
                "validate_answer",
                input={"draft": draft, "attempt": attempt},
                attributes={"semantic_type": "reasoning", "safety_level": "safe_read"},
            ) as validation_step:
                validation = validate_answer(draft)
                validation_step.output = {**validation, "attempt": attempt}

            final_answer = draft
            if not bool(validation["revision_required"]):
                break

            with step(
                "assess_progress",
                input={
                    "previous_doc_ids": [doc["id"] for doc in previous_docs],
                    "current_doc_ids": [doc["id"] for doc in docs],
                    "attempt": attempt,
                },
                attributes={"semantic_type": "reasoning", "safety_level": "safe_read"},
            ) as progress_step:
                progress = assess_progress(previous_docs, docs, attempt)
                progress_step.output = {**progress, "attempt": attempt}

            previous_docs = docs
            if bool(progress["stop_retry"]):
                break

        with step(
            "final_answer",
            input={"draft": final_answer},
            attributes={"semantic_type": "llm", "model": "demo-model", "safety_level": "safe_read"},
        ) as answer_step:
            answer_step.output = {"answer": final_answer}

        current_run.output = {
            "answer": final_answer,
            "revision_required": bool(validation["revision_required"]),
            "missing_concepts": list(validation["missing_concepts"]),
        }

    return current_run.id


def main() -> None:
    baseline = run_agent("agent-loop-baseline", precise_first_query=True)
    changed = run_agent("agent-loop-bounded-retry", precise_first_query=False)

    print("Created runs:")
    print(f"  baseline: {baseline}")
    print(f"  changed:  {changed}")
    print()
    print("Now try:")
    print(f"  trax diff {baseline} {changed}")
    print(f"  trax inspect {changed}")


if __name__ == "__main__":
    main()
