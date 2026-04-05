# RAG Failure

## What this example shows
A weaker query changes retrieval ranking, and the answer degrades because the workflow now sees incomplete evidence.

## Why it matters
In RAG systems, retrieval failures are often causal: query quality changes ranking, ranking changes evidence, and evidence changes the answer.

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
- retrieval output changed
- `reasoning:explain_retrieval` shows why ranking changed
- downstream answer changed
- the divergence starts before generation
