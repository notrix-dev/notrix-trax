# Notrix Trax

Debug AI workflows when they change unexpectedly.

Trace runs, diff executions, replay safely, and explain failures — locally.

---

When your LLM output changes, your agent behaves differently, or retrieval returns a different document…

Logs don’t tell you:
- what changed
- where the graph diverged
- which step caused the failure

**Trax does.**

---

## 60-second demo

```bash
pip install notrix-trax

trax list
trax inspect <run_id>
trax diff <run_a> <run_b>
trax explain <run_id>
trax replay <run_id> --start-at step_4 --stop-at step_8
```

Understand what changed. Reproduce only what matters. Fix faster.

---

## Example: LLM output changed unexpectedly

Two runs produce different answers.

Why?

- prompt changed?
- retrieval changed?
- tool behavior changed?

```bash
trax diff run_1 run_2
trax explain run_2
```

Trax shows:
- graph differences
- artifact changes
- detected failure points
- explanation grounded in evidence

---

## What Trax is (and isn’t)

**Trax is a debugger, not an observability platform.**

Not:
- dashboards
- metrics aggregation
- logging pipelines

Trax is for:
- understanding why behavior changed
- inspecting execution structure
- replaying safely
- explaining failures from evidence

---

## Quickstart

```bash
pip install -e .
trax --help
python examples/hero_diff_replay.py

trax list
trax inspect <run_id>
trax replay <run_id>
trax explain <run_id>
```

Trax stores:
- metadata in local SQLite
- artifacts on the filesystem (`TRAX_HOME`, default: `~/.trax`)

---

## CLI Overview

```bash
trax list
trax inspect <run_id>
trax diff <run_id_1> <run_id_2>
trax replay <run_id>
trax explain <run_id>
trax import-otel trace.json
```

---

## Minimal Adapter Usage

```python
from trax.adapters.openai import traced_chat
from trax.adapters.retrieval import traced_retrieval

docs = traced_retrieval(
    query="what is trax?",
    top_k=2,
    backend="simple_vector",
    retrieve=lambda **_: [{"id": "doc-1", "text": "Trax debugs AI runs."}],
)

response = traced_chat(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": "Summarize Trax."}],
    call=lambda **_: {"output_text": "Trax is a local-first AI debugger."},
)
```

---

## Ergonomic Capture

```python
from trax import run, step, traced_step

@traced_step("prepare", attributes={"semantic_type": "transform"})
def prepare_question(text: str) -> dict[str, str]:
    return {"normalized_question": text.strip().lower()}

with run("custom-flow", input={"question": "What does Trax do?"}):
    question = prepare_question("What does Trax do?")
    with step("answer", input=question, attributes={"semantic_type": "llm"}) as answer_step:
        answer_step.set_output({"answer": "Trax debugs AI workflows locally."})
```

---

## LangGraph integration (first-class support)

Trace real LangGraph execution at the graph boundary:

- invocation-level tracing
- node-level tracing
- no dependency on internal callbacks

Works with real compiled graphs — not simulated execution.

```python
from trax.langgraph import traced_invoke, traced_node
from langgraph.graph import END, START, StateGraph

graph = StateGraph(MyState)
# define nodes and edges...
compiled = graph.compile()

result = traced_invoke(compiled, {"question": "What does Trax do?"})
```

---

## Examples

- `examples/basic_capture/README.md` — smallest manual SDK capture flow
- `examples/rag_failure/README.md` — retrieval failure divergence across two runs
- `examples/agent_loop/README.md` — structural/path divergence across two runs
- `examples/langgraph_basic.py` — real LangGraph execution

---

## Core Concepts

- **Run**: one captured execution  
- **Step**: one traced unit of work  
- **Artifact**: persisted input/output  
- **Edge**: relationships between steps  

---

## Development

```bash
pip install -e .
pytest
```

---

## License

Apache License 2.0
