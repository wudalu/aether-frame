# Multi-Agent Roadmap: Planning, Task Board, Artifact Store

Key Takeaway:
- Primary focus is demand/requirement creation, not coding. Prioritize intent recognition and requirement structuring as first-class flows.
- Keep it small: ≤3 roles with strong contracts outperform swarms; use artifact-centric protocols over chat.
- Make Task Board and Artifact Store the shared backbone; treat them as APIs with schemas and leases, not just documents.
- Default pattern: Planner → Operator (ReAct) with optional Reviewer; enable lightweight Reflexion after failures.
- Acceptance-gated artifacts (diffs/docs/logs/tests) define “done” and drive decisions; chat is not the control surface.

Objective: Design collaboration patterns with a small number of agents (typically 2–3) to achieve better outcomes with lower complexity.

## Purpose & Document Structure

- Goal: establish a pragmatic collaboration approach for small teams of agents that minimizes overhead while improving reliability and outcome quality.
- Logic of this document:
  - Define industry-aligned best practices and why fewer agents are preferred (see Industry Best Practices).
  - Ground the design in concrete business scenarios and select patterns per scenario (see Business Scenarios & Analysis).
  - Synthesize a Solution Brief from research, scenarios, and current state; then detail core patterns and architecture (see Solution Brief).
  - Propose a framework-agnostic macro architecture and artifacts-first protocols to implement the collaboration model (see Architecture Design (Framework-Agnostic)).
  - Define Core Concepts & Terms to anchor components and shared services.
  - Map the design to ADK with specific components, hooks, and integration steps, while preserving ADK façade stability (see ADK Adaptation).
  - Keep research references and rationales for traceability (see References and Research Inputs & Rationale).

## Industry Research

- Fewer roles with strong contracts outperform large swarms due to reduced cognitive/context overhead (see Solution Brief and Quality Heuristics).
- Baseline Planner → Operator (ReAct) with optional Critic/Reviewer adds reliability where risk justifies the cost (see Core Patterns and Default Collaboration Pattern).
- Artifact-centric protocols (task board, evidence links, acceptance checklists) enable reproducibility and evaluation over chat transcripts (see Protocols and Schemas).
- Lightweight Reflexion notes after failures improve subsequent attempts without heavy tree search (see Optional Critic/Reviewer & Reflexion).
- Recent agents (Copilot Coding Agent, 2025 OpenAI Codex) emphasize a split between synchronous collaborator (in-editor) and asynchronous executor (cloud sandboxes per task, PR-first workflows).
- SWE-agent highlights deterministic ACI IO as a core design for LM reliability in code changes; Voyager/Manus show longer-horizon patterns (skills, recitation, KV-cache discipline).

### Research Alignment (Source of Truth)

- This roadmap derives from `docs/research/agents/README.md` (canonical index).
- Baseline: acceptance-gated artifacts; Plan→Executor with deterministic ACI IO; context discipline; minimal tool governance; trace-first evaluation; async/parallel as optional; reusable skills/memory.

## Research Inputs & Rationale

- ReAct + Reflexion papers show that interleaving reasoning/actions plus lightweight self-feedback improves task success without heavyweight tree search. Hence Planner→Operator baseline with Reflexion loops is prioritized, and ToT is optional.
- Claude Code internal practices emphasize a primary agent orchestrating a handful of sub-agents (writer/reviewer) with strong artifact output. That inspired the reviewer/critic option and artifact-first heuristics.
- Planner–Executor–Critic analyses highlight separation of planning vs execution for reliability; we adapt it via message schemas and acceptance checklists.
- Manus engineering notes underline context discipline and SOP-style collaboration, informing the blackboard/task board recommendations.
- Copilot/Codex indicate that parallel sandboxes can improve throughput; treat as an optional extension to avoid early complexity.
- SWE-agent/ACI show that deterministic tool IO improves LM reliability; incorporate ACI-like constraints in our tool layer.

 

## Business Scenarios & Analysis

- Demand/Requirement Creation (Primary)
  - Flow: intent elicitation → requirement structuring → acceptance criteria → PRD/briefs.
  - Required: Planner, Operator, Task Board, Artifact Store. Optional: Reviewer, Reflexion.
  - Protocol: evidence-linked decisions; Task Board gates for Goal/Out-of-scope/Personas/Scenarios/Acceptance; Artifact Store is source of truth.

- Research Synthesis & Decision Support
  - Flow: sources → evidence → synthesis → recommendation.
  - Required: Planner, Operator, Task Board, Artifact Store. Optional: Reviewer.
  - Protocol: artifacts = notes.md, table.csv, citations.json; Task Board enforces “evidence-before-synthesis”.

- Workflow Orchestration / No-Code Integrations
  - Flow: plan steps + stop conditions → ReAct execution → (optional) review.
  - Required: Planner, Operator, Task Board, Artifact Store. Optional: Reviewer, Parallelization.
  - Protocol: blackboard state, idempotent tool outputs, bounded retries by budgets.

General rule: ≤3 roles, 3–7 steps, step budgets, evidence-linked decisions; escalate to human on low confidence or policy violation. See Quality Heuristics.

## Current State Analysis

- ADK integration exists with `LlmAgent`, `SequentialAgent`, `ParallelAgent`, and `LoopAgent`; session/memory via Session Service and hooks in `src/aether_frame/agents/adk/adk_agent_hooks.py`.
- Collaboration flow prioritizes demand/requirement creation; coding/refactoring scenarios are de-emphasized.
- Task Board and Artifact Store specs are defined in this roadmap; implementation to start with Redis (leases/events) + filesystem/GCS for artifacts.
- Message schema, acceptance checklist, and evidence-linking patterns outlined; ADK adaptation will wire these into Planner/Operator lifecycles.

## Decision Matrix (Drivers & Trade-offs)

| Domain | Options Considered | Decision | Why | Trade-off | Switch Trigger |
| --- | --- | --- | --- | --- | --- |
| Team size & roles | Large swarms; Small (≤3 roles) | Small (≤3) with strong contracts | Less cognitive/context overhead; simpler recovery | Less parallel exploration | Low success rate under budget; consider enabling Reviewer more broadly |
| Collaboration mode | Chat-centric; Artifact-first | Artifact-first | Reproducibility, provenance, evaluation | Requires schema/URI discipline | If artifact overhead dominates, introduce generators for scaffolds |
| Core loop | Planner→Operator; Swarm | Planner→Operator baseline | Proven reliability without swarms | More responsibility on Operator | If repair loops remain high, add targeted Reviewer/Critic |
| Reviewer policy | Always-on; Risk-based | Risk-based (optional) | Cost-effective quality gates | Extra latency/cost when enabled | Non-compliance rate > threshold → enable on that scenario |
| Scheduling backbone (Task Board) | FS locks; Redis; Postgres; Temporal | Redis MVP | Native TTL/lease semantics; low-ops; we already use Redis | Needs HA (AOF/Sentinel/Cluster) | Lease conflict/reclaim/event-lag thresholds breached → add PG index / JetStream / Temporal; see survey |
| Artifact storage | FS only; S3/GCS; ML registries | FS(dev) → S3/GCS(prod) | Durable, cheap, standard SDKs; indexable | Eventual consistency; need index | Heavy lineage/metrics needs → add SQL/OLAP index / ML registry |
| Search depth | Heavy tree search; Light Reflexion | Light Reflexion | Faster loops; simpler scoring | May miss rare wins | If measurable uplift with discriminator, pilot deeper search |
| Execution model | Sync-only; Sync + Async background | Split: Sync collaborator + Async executor (optional) | Interactive productivity + batch throughput | Async scheduling & infra cost | Backlog & batch refactor queue justify background workers |

Note: Task Board/Artifact Store industry survey and detailed rationale live at `docs/research/taskboard_artifact_store_survey.md`.

## Solution Brief

Goal: Derive a small-team, artifact-first collaboration model optimized for demand/requirement creation, grounded by research, business scenarios, and current ADK capabilities. See Decision Matrix for the drivers and trade-offs that inform this brief. We adopt Plan → Executor (ReAct) as the core mode; async execution is an optional extension for batch/refactors.

Required components:
- Planner, Operator (ReAct), Task Board, Artifact Store.

Optional components:
- Reviewer/Critic, Reflexion notes, ParallelAgent + Synthesizer for fan-out/merge when justified.

Operating loop (high level)

```
User -> Planner -> Task Board -> Operator -> Artifact Store
                 (optional) Reviewer -> Planner
```

Contracts and protocols (essentials):
- Task Board with step gating and leases; Artifact Store with content-addressed artifacts and typed metadata.
- Message schema includes role/intent/step/artifacts/decision/confidence; acceptance checklists define “done”.

Why Plan → Executor is reasonable (concise):
- Reliability: single-step execution with deterministic tool IO mirrors SWE-agent’s evidence-led design and reduces failure surface.
- Cost shape: Manus shows KV-cache stability matters; stable prefixes pair well with stepwise, append-only traces.
- Governance: acceptance checklists and artifact gates apply cleanly to one-step outputs with clear done criteria.
- Extensibility: Reviewer/parallelization can be added behind the same contracts without re-architecting.

## Core Patterns (Required vs Optional)

- Required: Planner, Operator (ReAct loop), Task Board, Artifact Store.
- Optional: Reviewer/Critic, Reflexion notes, Parallelization (ParallelAgent), Synthesizer.
- Extension: Async executor (background sandboxes for batch/refactor)

Flow (required vs optional)

```
User -> Planner -> Task Board -> Operator -> Artifact Store
             \                                  /
              \--(optional) Parallel Agents ---/ -> Synthesizer
              (optional) Reviewer <---- review request ---- Operator
```

Capability Matrix

| Component/Pattern | Required | Optional |
| --- | :---: | :---: |
| Planner | ✓ |  |
| Operator (ReAct) | ✓ |  |
| Task Board | ✓ |  |
| Artifact Store | ✓ |  |
| Reviewer/Critic |  | ✓ |
| Reflexion Notes |  | ✓ |
| ParallelAgent |  | ✓ |
| Synthesizer |  | ✓ |

 

## Research ↔ Roadmap Mapping

| ID | Key Conclusion (agents/README) | Roadmap Category | Deliverables & Checks |
| --- | --- | --- | --- |
| C1 | Acceptance-gated artifacts | Required baseline | Message schema; acceptance checklists; Artifact Store with stable URIs; examples committed |
| C2 | Plan → Executor + deterministic ACI IO | Required baseline | Planner/Operator role contracts; typed tool IO; budgets/timeouts enforced in hooks |
| C3 | Context discipline & stability | Required baseline | Append-only traces; evidence links (artifact/store URIs); stable prefixes guidance |
| C4 | Minimal tool governance | Required baseline | MCP-first, small typed IO; tool timeouts/quotas; governance in hooks |
| C5 | Trace-first evaluation | Required baseline | Observability dashboards; scorecards + datasets; kill/switch criteria |
| C6 | Reviewer/Critic | Optional (risk-based) | Checklist-gated review; repair loop; escalation rules |
| C7 | Parallelization/Synthesizer | Optional (when justified) | Fan-out/merge; deterministic serialization; performance criteria |
| C8 | Async executor | Optional extension | Async executor POC; per-task sandbox; artifact PRs |
| C9 | Reusable skills/memory | Recommended (non-gating) | Small SOP skill library; externalized memory conventions |

## Architecture Design (Framework-Agnostic)

```
Architecture (framework-agnostic)

  User
    |
  Planner ---> Task Board ---> Operator ---> Artifact Store
                 ^                 |
                 |                 v
               (claims)          Tools/MCP

  Optional paths:
    Planner --(review req)--> Reviewer --(approve/repair)--> Planner
    Planner --(fan out)--> Parallel Agents --> Synthesizer --> Operator
```

Implementation notes (agnostic):
- Planner publishes steps and stop conditions to `Task Board`; Executors pull one step at a time and emit artifacts (drafts, logs, reports) to `Artifact Store`.
- Executors interact with `Tools/MCP` and read/write `Session/Memory` within step budgets; Synthesizer merges outputs when parallelism is used.
- Reviewer applies `Policies/Checklists` to artifacts and either approves, requests repair, or escalates to `Human`.
- All decisions cite artifact/evidence links for auditability.

## Core Concepts & Terms

- Planner: agent responsible for step planning, constraints, and stop conditions.
- Operator (ReAct): agent that executes steps via tool calls, producing observations and artifacts.
- Reviewer/Critic (optional): validates outputs against acceptance checklists; may request repair.
- Task Board: shared state (tasks, steps, leases, gates) enabling deterministic pull-based execution.
- Artifact Store: immutable evidence repository with content addressing (sha256) and typed metadata.
- Evidence Link: URI reference (e.g., `artifact://...`, `store://...`) cited in messages for auditability.
- Acceptance Checklist: per-step criteria used by Operator and Reviewer to judge completion.
- Reflexion Notes (optional): brief failure/self-correction notes guiding subsequent attempts.
- ParallelAgent/Synthesizer (optional): fan-out execution and result merging when parallelism helps.

## Task Board & Artifact Store (How-To + Examples)

See detailed industry survey and design guide:
`docs/research/taskboard_artifact_store_survey.md`.

Note:
- We follow Manus’s principle of using a persistent store for working memory and artifacts (FS locally, S3/GCS in prod), while separating scheduling (Task Board) from storage. File systems are not reliable for distributed claim/lease semantics.

Summary (high level)
- Task Board: claim/lease/heartbeat/complete; ready/claimed/in-progress; append-only events; deterministic pull-based execution.
- Artifact Store: immutable artifacts with SHA-256 integrity and stable URIs; index maintained; FS (dev) → S3/GCS (staging/prod).

For data models, state machines, API sketches, key layouts, MVP baseline, and evolution path, refer to `docs/research/taskboard_artifact_store_survey.md`.

Minimal API examples (sketch):

```
# Task Board
POST /tasks                                  -> {task_id}
POST /tasks/{id}/steps                       -> {step_id}
POST /tasks/{id}/steps/{sid}/claim           -> {lease_id, ttl}
POST /leases/{lease_id}/heartbeat            -> {ok}
POST /leases/{lease_id}/complete             -> {decision, artifacts[]}

# Artifact Store
PUT  /artifacts/{task}/{step} (multipart)    -> {artifact_id, sha256, uri}
GET  /artifacts/{task}/{step}                -> list
GET  /artifact?uri=artifact://T-1/S1/PRD.md  -> bytes
```

## ADK Adaptation (Components, Integration)

Component mapping (concise):

| Role | ADK Primitive | Notes |
| --- | --- | --- |
| Planner | PlanReActPlanner / BuiltInPlanner | Step creation, stop conditions |
| Operator | LlmAgent (SequentialAgent) | ReAct execution per step |
| Reviewer/Critic (opt) | LoopAgent / LlmAgent | Checklist-based evaluation |
| Parallelization (opt) | ParallelAgent + Synthesizer | Fan-out and merge |
| Shared services | Session Service + ExecutionContext | Plan metadata, artifact IDs, Redis Task Board |

Guardrails:
- Keep adk_adapter.py and adk_domain_agent.py as stable façades; extend via hooks/helpers.
- Bind session/memory and artifact routing in adk_agent_hooks.py.
- Enforce budgets/policies in hooks; persist artifact URIs and evidence links.

## Diagram (ADK-Oriented Flow)

```
ADK-Oriented Flow

  User
    |
  Planner --> SequentialAgent --> Operator --> Artifact Store
                 |                    ^
                 |                    |
                 +--> (optional) Reviewer --+
                 |
                 +--> (optional) ParallelAgent --> Synthesizer --> Operator
```





## Appendix: Core Pattern Details

1) Planner → Operator (ReAct) → Critic (Optional)
- Planner: decomposes goal into steps; sets acceptance criteria and tool policy.
- Operator: executes steps using a ReAct loop (Thought → Action(tool) → Observation), grounded by tools and memory.
- Critic/Judge: samples outputs or trajectories against the acceptance criteria; triggers repair loop when needed.

2) Writer–Reviewer Loop (Draft ↔ Review)
- Writer agent proposes drafts or structured outputs.
- Reviewer agent checks constraints (policy, completeness, style) and requests revisions.

3) Task Board / Blackboard
- Shared artifact (task list, state table) owned by the Coordinator or Planner; agents read/write without free-form chat.
- Encourages artifact-centric collaboration and reproducibility.

## Default Collaboration Pattern (Confirmed)

- Planner → Operator (ReAct) is the baseline for all flows; in requirement creation, Planner focuses on intent elicitation and scope gates; enable lightweight Reflexion after failures; add Critic/Reviewer only for high-risk scenarios.
- Operator emits structured evidence + artifacts; Critic checks acceptance checklist; Planner adjudicates conflicts / human-escalation.
- Keep role count ≤3, cap steps, and track budgets + evidence links per step.

## Protocols and Schemas

```
Entities (ASCII)
TASK contains STEP
STEP emits ARTIFACT
STEP logs MESSAGE
MESSAGE references TASK
ARTIFACT indexed_in TASK
```

Message schema (fields)

| Field | Type | Required | Note |
| --- | --- | :---: | --- |
| role | string | ✓ | operator, planner, reviewer |
| intent | string | ✓ | e.g., step_result |
| task_id | string | ✓ | e.g., T-2026-001 |
| step | number | ✓ | current step index |
| inputs | object |  | section, constraints |
| artifacts | string[] |  | artifact/store URIs |
| decision | string | ✓ | complete/repair/blocked |
| confidence | number |  | 0–1 |

## ReAct Integration (Operator)

```
ReAct Integration (ASCII)
User -> Planner: request/goal
Planner -> Task Board: publish steps
Operator -> Task Board: claim step (lease)
Operator -> Artifact Store: write artifacts (intent.md, PRD.md)
Operator -> Reviewer (optional): review request
Reviewer -> Planner: approve/repair
Planner -> Task Board: advance step / stop
```

## Optional Critic/Reviewer & Reflexion

- Reflexion: after failed steps or low-confidence outcomes, Operator records brief reflective notes (what failed, why, next attempt) into episodic memory to inform the next try.
- Reviewer: applies the acceptance checklist and policy constraints; requests targeted revisions. Use sparingly to avoid overhead.

## ADK Integration Notes (Concise)

- Planners: PlanReActPlanner/BuiltInPlanner drive steps/stop conditions.
- Hierarchy: LlmAgent, SequentialAgent, ParallelAgent, LoopAgent map to roles.
- Hooks: adk_agent_hooks.py binds session/memory and artifact routing.
- Session/memory: use Session Service + ExecutionContext; Redis backs Task Board.

## Quality Heuristics

- Prefer 2–3 roles; add a Critic only for high-risk tasks.
- Plan granularity: 3–7 steps; avoid micro-steps unless failure rate is high.
- Enforce step budgets (time/tokens/tool retries) to prevent drift.
- Require evidence links (artifacts) for critical decisions.

## References

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) (ICLR 2023) + [OpenReview discussion](https://openreview.net/forum?id=WE_vluYUL-X).
- [Claude Code: Best Practices for Agentic Coding](https://www.anthropic.com/engineering/claude-code-best-practices) (Anthropic Engineering, 2025-04-18).
- [Navigating Modern LLM Agent Architectures](https://www.wollenlabs.com/blog-posts/navigating-modern-llm-agent-architectures-multi-agents-plan-and-execute-rewoo-tree-of-thoughts-and-react) (Wollen Labs, 2025-07-17).
- [Context Engineering for AI Agents: Lessons from Building Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus) (2025-07-18).
- [ADK Documentation – Multi-Agent Patterns](https://github.com/google/adk-docs/blob/main/docs/agents/multi-agents.md).
- [Google Developers Blog – Developer’s guide to multi-agent patterns in ADK](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/).

## Implementation Roadmap (Editable Table)

| Phase | Timebox | Key Deliverables | Owner | Dependencies | Exit Criteria | Mapping |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 weeks | Task Board (Redis leases/events, HTTP/JSON API) | TBD | None | Create/list/claim/heartbeat/complete; ready/claimed/in-progress transitions; events stream | C2, C3, C4, C5 |
| 1 | 2 weeks | Artifact index + URIs (FS/S3), SHA-256, index.json | TBD | None | `put/get/list` APIs; artifact:// and store:// URIs; integrity verified | C1, C3, C5 |
| 1 | 2 weeks | Message schema + acceptance checklist templates | TBD | None | Schema published; checklists by domain; examples committed | C1, C2, C3 |
| 1 | 1 week | Hooks: Planner/Operator integrate TB/Store | TBD | Prior three | E2E flow: plan→claim→artifacts→review (opt) | C2, C4 |
| 2 | 2 weeks | Reviewer/Critic + Reflexion notes | TBD | Phase 1 | Checklist evaluation; repair loops; notes persisted | C6, C5 |
| 2 | 2 weeks | Parallelization + Synthesizer (when justified) | TBD | Phase 1 | Fan-out and merge with deterministic serialization | C7 |
| 2 | 2 weeks | Observability dashboards | TBD | Phase 1 | Leases, step latency, error/tool rate, cache hits | C5 |
| 2 | 2 weeks | Async executor POC (local Docker / thin remote worker) | TBD | Phase 1 | Run batch tasks in background; per-task sandbox; artifact PRs | C8 |
| 3 | 2 weeks | Scorecards + datasets | TBD | Phase 2 | Offline eval pass; acceptance-driven metrics live | C5 |
| 3 | 2 weeks | Retention/versioning + cloud mirror | TBD | Phase 2 | Lifecycle rules; cold storage; restore tested | C1, C3 |
| 3 | 1 week | Finalize SOPs + diagrams | TBD | Phase 2 | Docs merged; sign-off complete | C4, C9 |

Note: Keep diagrams ASCII-only for universal rendering.

## MVP → Enhanced Path

- MVP: Planner → Operator (ReAct), reflective notes after failed steps, acceptance checklist, artifact store, step budgets.
- Enhanced: optional Critic/Reviewer, reviewer loop (writer/reviewer for demand artifacts), blackboard task table, confidence-based auto-escalation to human.

## Protocol Templates

- Role contract (excerpt)
  - Planner.inputs: goal, constraints, acceptance_criteria
  - Planner.outputs: plan_steps[1..N], tool_policy, stop_conditions
  - Operator.inputs: step, current_context_pack
  - Operator.outputs: evidence_links[], artifacts[], step_result, confidence

- Message schema (JSON example)
  ```json
  {
    "role": "operator",
    "intent": "step_result",
    "task_id": "T-2026-001",
    "step": 3,
    "inputs": {"section": "Acceptance Criteria"},
    "artifacts": [
      "artifact://T-2026-001/S2/PRD.md",
      "artifact://T-2026-001/S2/acceptance_checklist.md",
      "store://logs/T-2026-001/S2/synthesis.log"
    ],
    "decision": "complete",
    "confidence": 0.82
  }
  ```

- Acceptance checklist (example)
  - PRD sections present (Goal, Personas, Scenarios, Out-of-scope)
  - Acceptance criteria complete and testable
  - Evidence cited (sources list) and artifact URIs valid
  - No PII in artifacts/logs; policy checks passed
  - Latency within target; retries within budget

## Example Flow (Textual)

- Planner creates a 4-step plan for a Meeting Assistant PRD; Operator executes step 1 (intent elicitation) via ReAct, uploads intent.md and personas.md; optional Reviewer flags missing privacy constraint → Operator repairs; Planner advances to step 2 (structure PRD) and produces PRD.md + acceptance_checklist.md; Reviewer approves; artifacts indexed.

## Open Questions

- What confidence threshold triggers Reviewer vs direct Planner adjudication?
- Which tasks require writer–reviewer loop vs Reviewer only?
- How to encode escalation to human with minimal friction?

## Task List (Planning Only)

- Draft role contracts and message schema catalog
- Define artifact store conventions and IDs
- Write acceptance checklist templates by domain
- Document human escalation SOPs

## Status

Draft
 
