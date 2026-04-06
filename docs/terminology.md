# Notrix Trax — Terminology Specification

**Status:** Stable  
**Version:** 1.0.0  
**Last Updated:** 2026-04-05  
**Maintainers:** Notrix Core Team  
**License:** Apache 2.0

---

## Core Concepts

| Term | Definition |
|---|---|
| **Run** | A single top-level execution instance |
| **Step** | A canonical, normalized unit of execution representing a single logical operation within a run |
| **Edge** | A directional, typed relationship between two steps |
| **Artifact** | Structured input or output data associated with a run or step, used for dependency resolution, replay/simulation, and diff |
| **Failure** | A deterministic condition derived from graph structure and/or artifacts that violates expected behavior or invariants |

---

## Graph Semantics

| Term | Definition |
|---|---|
| **Canonical graph** | The persisted, authoritative graph of steps and edges for a run |
| **Structural truth** | Facts about graph structure that are derived solely from persisted edges |
| **Root step** | A step with no incoming edges |
| **Dependency (conceptual)** | A logical requirement that one step relies on data or context from another step; **not a guaranteed persisted edge type** |
| **Control flow edge** | A fallback edge representing execution order without semantic dependency |

> Note: The current persisted edge types are implementation-defined (e.g., `parent_child`, `control_flow`). “Dependency” is a conceptual term and MUST NOT be assumed to map 1:1 to a stored edge.

---

## Capture & Normalization

| Term | Definition |
|---|---|
| **Capture signal** | A raw event emitted by an SDK, adapter, or instrumentation layer |
| **Normalizer** | The component responsible for assigning canonical meaning to raw signals |
| **Scope hint** | A non-structural metadata field emitted by SDKs or adapters (e.g., `scope_parent_step_id`) |
| **Evidence** | Structured information derived from capture signals used by the normalizer to construct steps and edges |

---

## Replay / Simulation

> **Important:** Current implementation is **simulation-only, artifact-backed replay**, not live re-execution.

| Term | Definition |
|---|---|
| **Replay (simulation)** | Deterministic reconstruction and simulation of a run (or subset) using the canonical graph and recorded artifacts |
| **Replay window** | The subset of steps selected for simulation |
| **Simulated step** | A step whose behavior is reconstructed from recorded artifacts without executing external code |
| **Skipped step** | A step not simulated because it is not required for the selected window |

> Future versions MAY support live execution modes. Terminology here reflects current behavior.

---

## Diff & Analysis

| Term | Definition |
|---|---|
| **Diff** | A comparison between two runs at graph, artifact, or failure level |
| **Baseline run** | The original run used as reference for comparison |
| **Compared run** | The run being evaluated against a baseline |
| **Change surface** | The set of differences detected between runs |

---

## Execution Semantics

| Term | Definition |
|---|---|
| **Execution boundary** | The boundary at which a step is captured and normalized |
| **Deterministic step** | A step that produces identical outputs given identical inputs |
| **Non-deterministic step** | A step whose output may vary despite identical inputs |

---

## Derived Views

| Term | Definition |
|---|---|
| **Projection** | Any derived view of the canonical graph (UI, CLI, export) |

---

## Notes

- Terminology defined here MUST be used consistently across all specifications.
- Definitions are normative unless otherwise stated.
- This document serves as the shared language layer for:
  - system-spec.md
  - spec-graph.md
  - spec-replay.md
  - spec-diff-detect.md
  - spec-adapter.md
- This document reflects **current implementation behavior**, not future intent.
