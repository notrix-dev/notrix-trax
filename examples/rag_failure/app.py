"""Deterministic RAG example showing causal retrieval degradation."""

from __future__ import annotations

import re

from trax import run, step

QUESTION = "What does Trax do?"
TOP_K = 2
CORPUS = [
    {
        "id": "doc-1",
        "title": "Trax debugger",
        "text": "Trax captures AI runs, diffs execution graphs, replays safely, and explains failures.",
        "concepts": ["captures_ai_runs", "diffs_execution_graphs", "replays_safely", "explains_failures"],
    },
    {
        "id": "doc-2",
        "title": "Tracing basics",
        "text": "Tracing tools record steps, artifacts, and metadata for debugging workflows.",
        "concepts": ["steps", "artifacts", "metadata"],
    },
    {
        "id": "doc-3",
        "title": "Metrics dashboard",
        "text": "A metrics dashboard aggregates latency charts across many services.",
        "concepts": ["metrics", "latency", "dashboard"],
    },
]
TARGET_CONCEPTS = {
    "captures_ai_runs": "captures AI runs",
    "diffs_execution_graphs": "diffs execution graphs",
    "explains_failures": "explains failures",
}


def rewrite_query(question: str, *, include_core_product_terms: bool) -> str:
    del question
    if include_core_product_terms:
        return "Trax AI runs diff explain debugger"
    return "trace dashboard metrics"


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def retrieve_docs(query: str) -> list[dict[str, object]]:
    query_terms = _tokenize(query)
    scored_docs: list[tuple[int, dict[str, object]]] = []
    for doc in CORPUS:
        text_terms = _tokenize(f"{doc['title']} {doc['text']}")
        score = len(query_terms & text_terms)
        scored_docs.append((score, doc))
    ranked = sorted(scored_docs, key=lambda item: (-item[0], item[1]["id"]))
    return [
        {
            "id": doc["id"],
            "text": doc["text"],
            "score": score,
            "concepts": list(doc["concepts"]),
        }
        for score, doc in ranked[:TOP_K]
    ]


def explain_retrieval(query: str, docs: list[dict[str, object]]) -> dict[str, object]:
    query_terms = _tokenize(query)
    concept_tokens = {
        concept: _tokenize(label)
        for concept, label in TARGET_CONCEPTS.items()
    }
    ranked_missing_concepts = [
        concept
        for concept, _label in TARGET_CONCEPTS.items()
        if not concept_tokens[concept] & query_terms
    ]
    key_missing_concept = ranked_missing_concepts[0] if ranked_missing_concepts else None
    top_doc = docs[0]
    top_doc_concepts = set(top_doc["concepts"])
    selected_doc_incomplete_concepts = [
        label
        for concept, label in TARGET_CONCEPTS.items()
        if concept not in top_doc_concepts
    ]
    if key_missing_concept is not None:
        missing_label = TARGET_CONCEPTS[key_missing_concept]
        ranking_reason = (
            f"Query is missing '{missing_label}', so lexical overlap shifts toward {top_doc['id']}."
        )
        incomplete_reason = (
            f"{top_doc['id']} does not cover '{missing_label}', so the retrieved evidence is incomplete."
        )
    else:
        ranking_reason = f"Query includes core product terms, so {top_doc['id']} ranks first."
        incomplete_reason = f"{top_doc['id']} covers the core product concepts needed for the answer."
    return {
        "missing_query_concept": TARGET_CONCEPTS[key_missing_concept] if key_missing_concept is not None else None,
        "ranking_reason": ranking_reason,
        "selected_doc_id": top_doc["id"],
        "selected_doc_score": top_doc["score"],
        "selected_doc_incomplete_concepts": selected_doc_incomplete_concepts,
        "incomplete_reason": incomplete_reason,
    }


def extract_facts(doc: dict[str, object]) -> list[str]:
    facts: list[str] = []
    text = str(doc["text"]).replace(".", "")
    text = text.replace(" and ", ", ")
    parts = [part.strip() for part in text.split(",") if part.strip()]
    for part in parts:
        cleaned = re.sub(r"^Trax\s+", "", part).strip()
        if cleaned:
            cleaned = cleaned[0].lower() + cleaned[1:]
        if cleaned:
            facts.append(cleaned)
    return facts


def join_facts(facts: list[str]) -> str:
    if not facts:
        return "works from the available local evidence"
    if len(facts) == 1:
        return facts[0]
    if len(facts) == 2:
        return f"{facts[0]} and {facts[1]}"
    return f"{', '.join(facts[:-1])}, and {facts[-1]}"


def generate_answer(docs: list[dict[str, object]]) -> str:
    primary_doc = docs[0]
    primary_facts = extract_facts(primary_doc)[:2]
    return f"Trax {join_facts(primary_facts)}."


def run_pipeline(name: str, *, include_core_product_terms: bool) -> str:
    with run(name, input={"question": QUESTION}) as current_run:
        with step(
            "rewrite_query",
            input={"question": QUESTION},
            attributes={"semantic_type": "transform", "safety_level": "safe_read"},
        ) as query_step:
            retrieval_query = rewrite_query(QUESTION, include_core_product_terms=include_core_product_terms)
            query_step.output = {"query": retrieval_query}

        with step(
            "retrieve_docs",
            input={"query": retrieval_query},
            attributes={
                "semantic_type": "retrieval",
                "backend": "demo_search",
                "top_k": TOP_K,
                "safety_level": "safe_read",
            },
        ) as retrieval_step:
            docs = retrieve_docs(retrieval_query)
            retrieval_step.output = {"docs": docs}

        with step(
            "explain_retrieval",
            input={"query": retrieval_query, "docs": docs},
            attributes={"semantic_type": "reasoning", "safety_level": "safe_read"},
        ) as explain_step:
            retrieval_explanation = explain_retrieval(retrieval_query, docs)
            explain_step.output = retrieval_explanation

        with step(
            "generate_answer",
            input={"question": QUESTION, "docs": docs},
            attributes={
                "semantic_type": "llm",
                "model": "demo-model",
                "temperature": 0.1,
                "safety_level": "safe_read",
            },
        ) as answer_step:
            answer = generate_answer(docs)
            answer_step.output = {"answer": answer}

        current_run.output = {
            "answer": answer,
            "retrieval_query": retrieval_query,
            "retrieval_explanation": retrieval_explanation,
        }

    return current_run.id


def main() -> None:
    baseline = run_pipeline("rag-failure-baseline", include_core_product_terms=True)
    failed = run_pipeline("rag-failure-degraded-retrieval", include_core_product_terms=False)

    print("Created runs:")
    print(f"  baseline: {baseline}")
    print(f"  failed:   {failed}")
    print()
    print("Now try:")
    print(f"  trax diff {baseline} {failed}")
    print(f"  trax inspect {failed}")
    print(f"  trax explain {failed}")


if __name__ == "__main__":
    main()
