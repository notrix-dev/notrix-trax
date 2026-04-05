# Agent Loop Behavior

## What this example shows
A multi-step workflow that enters a bounded retry loop when validation keeps finding missing coverage.

## Why it matters
Agent failures are often structural:
- repeated retrieval and validation phases
- a retry path
- a stop condition because progress stalls

## Run it
```bash
python examples/agent_loop/app.py
```

## Inspect it
```bash
trax diff <baseline_run_id> <changed_run_id>
trax inspect <changed_run_id>
```

## What to notice
Trax highlights the repeated retry pattern and where the workflow stops because the evidence is still weak.
