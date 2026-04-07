# RAG Failure

## What this example shows
A weaker query misses a key concept, retrieval returns no docs, and the answer degrades because the workflow now has no evidence.

## Why it matters
In RAG systems, retrieval failures are often causal: query quality changes evidence, evidence changes the answer, and `trax explain` can surface the failure directly.

## Run it
```bash
python examples/rag_failure/app.py
```

## Inspect the retrieval step
```bash
trax diff <baseline_run_id> <changed_run_id>
trax inspect <changed_run_id>
trax explain <changed_run_id>
```

## What to notice
- query rewrite changed
- retrieval output became empty
- `reasoning:explain_retrieval` shows why ranking changed
- `trax explain` now surfaces a real retrieval failure instead of `No issues detected`
- downstream answer changed
- the divergence starts before generation
