# Contributing to Notrix Trax

Notrix Trax is a **canonical execution intelligence system** for debugging non-deterministic AI workflows. It turns runtime signals into structured, replayable, and explainable execution truth.

This guide explains how to contribute effectively — whether you're fixing a bug, building a new adapter, or improving the spec.

---

## Table of Contents

1. [Before You Start](#1-before-you-start)
2. [How the System Works](#2-how-the-system-works)
3. [Ways to Contribute](#3-ways-to-contribute)
4. [Local Setup](#4-local-setup)
5. [Making a Change](#5-making-a-change)
6. [Pull Request Guidelines](#6-pull-request-guidelines)
7. [Reporting Bugs](#7-reporting-bugs)
8. [Proposing Features](#8-proposing-features)
9. [Design Rules](#9-design-rules)
10. [Code of Conduct](#10-code-of-conduct)

---

## 1. Before You Start

**Good first issues** are tagged [`#good-first-issue`](https://github.com/notrix-dev/notrix-trax/issues?q=is%3Aissue+label%3A%22good+first+issue%22) on GitHub. If you want to work on something, leave a comment on the issue so others know.

For larger changes — new subsystems, changes to the normalizer or graph layer, or anything that touches a spec — **open an issue first**. This avoids doing work that doesn't align with the project's direction.

You don't need to understand the entire system to contribute. Adapters, documentation, and CLI improvements are all self-contained and a good entry point.

---

## 2. How the System Works

Understanding one key distinction makes everything else fall into place:

> **Trax is not an observability tool. It is a deterministic debugging system.**

Observability tools pass traces through and display them. Trax *constructs* a canonical execution graph from raw signals — stripping provider-specific details, resolving structural relationships, and producing something that can be diffed, replayed, and explained reliably.

### The Pipeline

```
Capture → Collect → Normalize → Persist → Graph → Diff / Detect / Replay → Explain → UI
```

Each stage has a defined job and a defined authority boundary:

| Layer | Job | Can write canonical data? |
|---|---|---|
| Adapter | Emit capture signals | No |
| Normalizer | Assign canonical meaning to steps | **Yes** |
| Graph | Assert structural edges | **Yes** |
| Diff / Detect / Replay | Derive insights from the graph | No (read-only) |
| Explain | Interpret canonical + derived data | No |
| CLI / UI | Project data for display | No |

The **Normalizer** is the only place where raw signals get canonical meaning assigned. In the current implementation, fallback `control_flow` edges may also be constructed during normalization, while the **Graph** remains the canonical structural validation layer. Everything downstream reads from those sources — it never writes back to them.

If you're not sure which layer your change belongs to, open an issue and ask.

---

## 3. Ways to Contribute

### Build an Adapter ← great starting point

Adapters capture execution signals from AI frameworks and pass them to the collector. This is the highest-impact area for new contributors and the most self-contained.

**Frameworks we'd love to see:**
- OpenAI Assistants API
- CrewAI
- AutoGen
- LlamaIndex
- Haystack
- Custom / proprietary frameworks

**What an adapter does:**
- Intercepts execution events from a framework
- Emits `CollectedEvent` signals to the Trax collector
- Optionally includes scope hints (e.g., `scope_parent_step_id`) as metadata

**What an adapter must not do:**
- Define canonical step meaning — that's the Normalizer's job
- Emit canonical edges — that's the Graph's job
- Bypass the collector or write directly to the canonical graph

See `trax/adapters/` for existing examples and `docs/spec-adapter.md` for the full contract.

---

### Improve the Core System ← requires prior discussion

The normalizer, graph, replay, and diff subsystems are the heart of Trax. Changes here have cascading effects.

**If you want to work on:**
- Adding a new canonical step type (e.g., `memory:read`, `embedding:encode`)
- Improving edge construction rules
- Extending replay safety levels
- Improving diff accuracy

**You should:**
1. Open an issue describing the change and its motivation
2. Reference the relevant spec (`spec-normalizer.md`, `spec-graph.md`, etc.)
3. Identify any downstream effects using the spec dependency graph
4. Get sign-off before writing code

Core system PRs require review from two maintainers.

---

### CLI and UX Improvements ← welcome, with limits

The CLI is a projection layer — it displays canonical and derived data but never modifies it.

**Welcome:**
- New output formats and `--view` modes
- Formatting and readability improvements
- New commands that expose existing data in useful ways

**Not permitted:**
- Logic that modifies system behavior
- Inference or transformation beyond formatting
- Any write-back to the canonical or derived layers

---

### Documentation and Specs

Highly encouraged. The spec system (`docs/`) is the source of truth for system behavior. Clear specs make better implementations.

**Good documentation contributions:**
- Clarifying ambiguous spec language
- Adding worked examples to specs
- Improving onboarding guides
- Fixing errors or outdated information

For normative spec changes (anything that changes what an implementation must do), follow the spec contribution process in `docs/system-spec.md`.

---

### Bug Fixes

Bug fixes are always welcome. For bugs in the core system, please include a minimal reproduction and a reference to the invariant or rule being violated (e.g., "this violates G-3 from `spec-graph.md`").

---

## 4. Local Setup

```bash
git clone https://github.com/notrix-dev/notrix-trax.git
cd notrix-trax

pip install -e .
pip install -r requirements.txt
```

Verify your setup:

```bash
python examples/hero_diff_replay.py
```

Run the test suite:

```bash
pytest
```

### Project Structure

```
trax/
  adapters/        # capture layer — emit signals from frameworks
  normalizer/     # semantic authority — assigns canonical step meaning
  graph/          # structural authority — constructs and validates edges
  replay/         # deterministic replay engine
  diff/           # two-run comparison engine
  detect/         # single-run failure detection
  cli/            # projection only — never modifies system state

examples/         # runnable demos
docs/             # spec system — source of truth for system behavior
```

---

## 5. Making a Change

1. **Fork and clone the repo.** Click **Fork** on GitHub, then clone your fork locally.
   ```bash
   git clone https://github.com/<your-username>/trax.git
   cd notrix-trax
   git remote add upstream https://github.com/notrix-dev/notrix-trax.git
   ```
   Adding `upstream` lets you pull in future changes from the main repo:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Create a branch** from `main`.
   ```bash
   git checkout -b your-area/short-description
   ```

3. **Make your change.** Keep commits focused — one logical change per commit.

4. **Write tests.** New behavior needs unit tests. New adapters need at least one integration example in `examples/`.

5. **Check naming consistency.** Step names follow `<domain>:<operation>` (e.g., `llm:call`, `retrieval:query`, `tool:invoke`). Provider-specific names are not permitted in canonical step types.

6. **Run the full test suite** before opening a PR.
   ```bash
   pytest
   ```

7. **Open a pull request** using the template in [Section 6](#6-pull-request-guidelines).

---

## 6. Pull Request Guidelines

### Title format

```
[area] short description
```

Examples:
```
[adapter] add CrewAI execution capture
[graph] fix cycle detection for parallel root steps
[docs] clarify fallback edge rules in spec-graph
[cli] add --format json output to diff command
```

### What to include in the PR body

- **What changed** — a clear description of the change
- **Why it's needed** — motivation, linked issue if applicable
- **Which layer is affected** — adapter / normalizer / graph / derived / cli
- **Spec implications** — does this change require a spec update? If so, include it in the same PR
- **How to test** — steps to verify the change works

### Review requirements

| Change type | Required reviewers |
|---|---|
| Adapter, CLI, docs | 1 maintainer |
| Core system (normalizer, graph, replay, diff) | 2 maintainers |
| Spec changes (normative) | 2 maintainers |
| Conformance requirements | 2 maintainers + issue discussion |

---

## 7. Reporting Bugs

Open a [GitHub Issue](https://github.com/notrix-dev/notrix-trax/issues/new) with:

- A clear description of the unexpected behavior
- Steps to reproduce (minimal reproduction preferred)
- Expected behavior vs. actual behavior
- The `run_id` if the bug is graph-related
- Which spec invariant or rule is being violated, if you can identify it

For security issues, please do not open a public issue. Email `security@notrix.dev` instead.

---

## 8. Proposing Features

Open a GitHub Issue before building anything significant.

**We're excited about:**
- New framework adapters
- Replay safety improvements
- Diff and detect accuracy improvements
- Developer experience and CLI improvements

**We're cautious about:**
- Observability-style pass-through features
- Automatic instrumentation or monkey-patching
- Heuristics that change behavior silently
- Anything that adds inference at the projection layer

A good feature proposal explains what problem it solves, which layer it belongs to, and whether it requires a spec change.

---

## 9. Design Rules

These rules are non-negotiable. PRs that violate them will not be merged regardless of other quality.

**No hidden behavior.** All behavior must be explicit, inspectable, and reproducible. No implicit instrumentation, no silent heuristics, no auto-detection that changes output without an explicit opt-in.

**Authority boundaries are hard.** Adapters do not define structure. The Normalizer is the only semantic authority. The Graph is the only structural authority. Derived systems and the UI are read-only. These are not conventions — they are invariants.

**Canonical naming is stable.** Step names (`<domain>:<operation>`) are immutable once registered. Do not introduce provider-specific names, positional suffixes, or dynamically generated names.

**Projection never writes back.** Nothing in the CLI or UI layer may mutate canonical or derived state. If you find yourself needing to, the change belongs in a different layer.

**Determinism is required.** The same inputs must always produce the same outputs in the normalizer, graph, diff, and detect subsystems. Non-deterministic behavior is a bug.

For the full system-level contract, see `spec-system.md`.

---

## 10. Code of Conduct

Trax follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). Be respectful, be constructive, and assume good intent.

---

Every contribution — whether it's a new adapter, a spec clarification, or a one-line fix — helps make AI systems more understandable, debuggable, and reliable. We're glad you're here.
