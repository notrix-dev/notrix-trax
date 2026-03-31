# notrix-trax

Trax is a local-first AI debugging tool for capturing runs, reconstructing execution graphs, replaying behavior safely, and generating evidence-based explanations.

Core concepts:
- `Run`: one captured execution
- `Step`: one traced unit of work inside a run
- `Artifact`: persisted input/output payloads
- `Edge`: relationships between steps in the execution graph

## Quickstart

```bash
pip install -e .
trax --help
python examples/rag-example/app.py
trax list
trax inspect <run_id>
trax replay <run_id>
trax explain <run_id>
```

The CLI stores metadata in local SQLite and artifacts on the filesystem under `TRAX_HOME` (default: `~/.trax`).

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

## CLI Commands

```bash
trax list
trax inspect <run_id>
trax diff <run_id_1> <run_id_2>
trax replay <run_id>
trax explain <run_id>
trax import-otel trace.json
```

## Examples

- `examples/rag-example/README.md`: retrieval + LLM flow using the adapter layer
- `examples/agent-example/README.md`: simple multi-step workflow showing graph structure and a detectable failure

## Development

```bash
pip install -e .
pytest
```
