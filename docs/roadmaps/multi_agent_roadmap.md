# Multi-Agent Roadmap (Executive Summary)

Purpose: Provide a concise, stakeholder-friendly overview of why we chose this approach, what the solution is, how we plan to deliver it, and who owns what. Details live in `multi_agent_one_page.md`.

## 1) Rationale & Logic (Why this approach)

- Drivers: reliability, cost/latency, governance. Small teams of agents (≤3) with strong contracts outperform swarms under practical constraints.
- Evidence: industry research (Claude Code, Manus, SWE-agent, Copilot/Codex) supports acceptance-gated artifacts and a Plan → Executor loop with deterministic tool IO.
- Core logic: fewer roles, artifact-first collaboration, typed/deterministic tools, append-only traces, and optional extensibility (Reviewer/Parallel/Async) when justified by metrics.

## 2) Solution Brief (What we’re building)

Core idea:
- Baseline pattern = Planner → Operator (ReAct), acceptance-gated artifacts, Task Board (leases/events), Artifact Store (content-addressed URIs), message schema + checklists.
- Optional modules (risk/throughput driven) = Reviewer/Critic, Parallelization + Synthesizer, Async executor (per-task sandbox for batches/refactors).

Architecture (ASCII):
```
User
  |
Planner ---> Task Board ---> Operator ---> Artifact Store
               ^                 |
               |                 v
             (claims)          Tools/MCP

Optional:
  Planner --(review req)--> Reviewer --(approve/repair)--> Planner
  Planner --(fan out)--> Parallel Agents --> Synthesizer --> Operator
```

Required vs Optional:
- Required: Planner, Operator (ReAct), Task Board, Artifact Store.
- Optional: Reviewer/Critic, Reflexion notes, Parallelization/Synthesizer, Async executor.

Key details (expanded):

- Core contracts & invariants
  - Message schema: `role, intent, task_id, step, inputs, artifacts[], decision, confidence` (append-only; stable serialization).
  - Acceptance-gated artifacts: each step’s “done” is defined by a checklist; Operator must attach evidence links (artifact://, store:// URIs).
  - Budgets: per-step limits on time/tokens/tool retries; enforce in hooks; escalate on low confidence.

- Task Board (scheduling essentials)
  - Deterministic pull: `ready → claimed → in_progress → done/blocked` with leases + heartbeat; idempotent `complete` by lease_id.
  - Events: append-only stream for observability and replay (reindex/forensics).
  - Ready list: enable “one-step-at-a-time” execution to preserve KV‑cache stability and reduce failure surface.

- Artifact Store (evidence essentials)
  - Content-addressed artifacts (SHA‑256) with stable URIs; index.json per task for quick lookup and lineage.
  - Storage path: FS (dev) → S3/GCS (staging/prod); logs under `store://logs/{task}/{step}/...`.
  - Typical demand artifacts: `intent.md`, `personas.md`, `PRD.md`, `acceptance_checklist.md`, `synthesis.log`.

- Operator ACI IO (deterministic tools)
  - Typed tool inputs/outputs; predictable shapes; no locale/date randomness; canonical JSON when applicable.
  - Small, LM‑friendly tool surface via MCP; timeouts/quotas per tool call; idempotent write operations.

- Acceptance & governance
  - Checklists per domain (e.g., PRD completeness, testability, policy). Reviewer (optional) samples outputs and triggers repair.
  - Trace‑first: decisions derive from artifacts/logs; store evidence links in messages for auditability.

- Risk controls & kill/switch
  - Indicators: step latency p95, tool error rate, reclaim/churn, cache‑hit ratio (where applicable).
  - Kill/switch: auto‑escalate to Reviewer or Human when non‑compliance or low confidence crosses thresholds.

- Extensibility toggles (when to enable)
  - Reviewer: high‑risk domains or repeated low confidence.
  - Parallelization/Synth: batch/refactor workloads with ≥1.5× speedup at acceptable cost.
  - Async executor: backlog requires background throughput; per‑task sandbox, PR‑first results.

## 3) Implementation Roadmap (fill timeboxes; table + ASCII Gantt)

Editable table (Timebox to be filled by stakeholders):

| Phase | Timebox | Key Deliverables | Owner | Dependencies | Exit Criteria |
| --- | --- | --- | --- | --- | --- |
| 1 | [   ] | Task Board (Redis leases/events, HTTP/JSON API) | [   ] | None | Create/list/claim/heartbeat/complete; ready/claimed/in-progress; events stream |
| 1 | [   ] | Artifact index + URIs (FS/S3), SHA-256, index.json | [   ] | None | `put/get/list` APIs; artifact:// and store:// URIs; integrity verified |
| 1 | [   ] | Message schema + acceptance checklist templates | [   ] | None | Schema published; checklists by domain; examples committed |
| 1 | [   ] | Hooks: Planner/Operator integrate TB/Store | [   ] | Prior three | E2E flow: plan→claim→artifacts→review (opt) |
| 2 | [   ] | Reviewer/Critic + Reflexion notes | [   ] | Phase 1 | Checklist evaluation; repair loops; notes persisted |
| 2 | [   ] | Parallelization + Synthesizer (when justified) | [   ] | Phase 1 | Fan-out and merge with deterministic serialization |
| 2 | [   ] | Observability dashboards | [   ] | Phase 1 | Leases, step latency, error/tool rate, cache hits |
| 2 | [   ] | Async executor POC (local Docker / thin worker) | [   ] | Phase 1 | Background tasks; per-task sandbox; artifact PRs |
| 3 | [   ] | Scorecards + datasets | [   ] | Phase 2 | Offline eval; acceptance-driven metrics live |
| 3 | [   ] | Retention/versioning + cloud mirror | [   ] | Phase 2 | Lifecycle rules; restore tested |
| 3 | [   ] | Finalize SOPs + diagrams | [   ] | Phase 2 | Docs merged; sign-off complete |

ASCII Gantt (draft — widths illustrative, align with your timeboxes):
```
Phase 1: |##########|  TB/API
         |##########|  Artifact index/URIs
         |######    |  Schema + checklists
         |###       |  Hooks (Planner/Operator)

Phase 2:       |########|  Reviewer + Reflexion
               |######  |  Parallel + Synth
               |######  |  Observability
               |######  |  Async executor POC

Phase 3:                 |#####|  Scorecards + datasets
                         |#####|  Retention + cloud mirror
                         |###  |  SOPs + diagrams
```

## 4) Related Modules & Stakeholders

| Module | Primary Owner | Stakeholders | Dependencies | Notes |
| --- | --- | --- | --- | --- |
| Task Board (Redis leases/events) | [   ] | Platform Eng, SRE | Redis/infra | Idempotent complete; leases + visibility timeout |
| Artifact Store (FS→S3/GCS + index) | [   ] | Platform Eng, Security | Cloud storage | SHA-256 integrity; stable URIs; retention |
| Message schema + checklists | [   ] | Product, QA | — | Acceptance-gated artifacts; domain templates |
| Planner/Operator hooks | [   ] | Product, App Teams | Task Board, Artifact Store | E2E plan→execute→artifact flow |
| Reviewer/Critic (opt) | [   ] | QA, Risk/Compliance | Schema/templates | Risk-based enablement |
| Parallelization/Synth (opt) | [   ] | Platform Eng | Hooks | Throughput-driven; deterministic merge |
| Observability | [   ] | SRE, Data | All above | Leases/latency/errors/cache-hit |
| Async executor POC (opt) | [   ] | Platform Eng | TB/Store | Per-task sandbox; PR-first |

References: detailed design lives in `docs/roadmaps/multi_agent_one_page.md` and `docs/research/agents/README.md`.
