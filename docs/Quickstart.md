
# Quickstart
---

## STEP 1 — INSTALL

```bash
pip install notrix-trax
```

---

## STEP 2 — RUN

```bash
python examples/hero_diff_replay.py
```

Expected:

```text
Created runs:
  baseline: <run_id_a>
  changed:  <run_id_b>

Now try:
  trax list
  trax diff <run_id_a> <run_id_b>
  trax explain <run_id_b>
  trax replay <run_id_b>
```

---

## STEP 3 — CLI FLOW 


### List Runs

```bash
trax list
```

Expected:

```text
Runs:
- <run_id_b>
  Name: quickstart-changed
  Status: completed
- <run_id_a>
  Name: quickstart-baseline
  Status: completed
```

---

### Diff Runs

```bash
trax diff <run_id_a> <run_id_b>
```

Expected:

```text
Summary:
  steps_modified: 2
  output_changed: yes
  key_config_changes: temperature, top_k

Step Diff:
[MODIFIED] retrieve_docs
  attrs:
    top_k: 2 -> 1
  output: changed
[MODIFIED] generate_answer
  attrs:
    temperature: 0.2 -> 0.9
  output: changed
Metrics:
  latency_ms: [X]ms
  tokens: n/a
  cost: n/a
```

---

### Explain

```bash
trax explain <run_id_b>
```

Expected:

```text
Run:
Run: <run_id_b>

Failure: ...
Likely causes:
- ...
Suggestions:
- ...
```

---

### Replay

```bash
trax replay <run_id_b>
```

Expected:

```text
Replay:
Replay: <run_id_b>
Status: completed
Replay Window: run-start -> run-end
Simulated Steps: 2
Blocked Steps: 0
Skipped Steps: 0
[SIMULATED] retrieve_docs
[SIMULATED] generate_answer
```

---

## OPTIONAL — LANGGRAPH EXECUTION-BOUNDARY PATH

Run:

```bash
python examples/langgraph_basic.py
```

Core call:

```python
result = traced_invoke(graph, input_payload)
```

Then:

```bash
trax list
trax inspect <run_id>
trax explain <run_id>
```

This integration traces real LangGraph execution at the invocation and node boundary. It does not depend on LangGraph internal callbacks or runtime events.
