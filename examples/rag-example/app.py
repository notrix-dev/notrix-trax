"""Minimal RAG-style Trax example."""

from __future__ import annotations

from trax.adapters.openai import traced_chat
from trax.adapters.retrieval import traced_retrieval


def main() -> None:
    docs = traced_retrieval(
        query="What does Trax do?",
        top_k=2,
        backend="simple_vector",
        retrieve=lambda **_: [
            {"id": "doc-1", "text": "Trax captures and explains AI runs."},
            {"id": "doc-2", "text": "Trax is local-first and CLI driven."},
        ],
    )
    response = traced_chat(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": f"Answer using these docs: {docs}",
            }
        ],
        call=lambda **_: {
            "output_text": "Trax is a local-first AI debugging tool.",
            "usage": {"total_tokens": 42},
        },
    )
    print(response["output_text"])


if __name__ == "__main__":
    main()
