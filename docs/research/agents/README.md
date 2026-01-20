# Agent Research Index

Status: Draft
Last updated: 2026-01-19

This index is the canonical summary for the entire `agents/` folder. It aggregates and stabilizes content across individual briefs, reflecting the latest changes. Downstream roadmaps — executive (`docs/roadmaps/multi_agent_roadmap.md`) and full (`docs/roadmaps/multi_agent_one_page.md`) — must align with the conclusions and adoption guidance captured here.

## Scope & Canonical Role

- Canonical aggregator of research findings under `docs/research/agents/`.
- Single source of truth for: prioritized conclusions, adoption guide, thresholds, and metrics.
- Feeds the Roadmap: `docs/roadmaps/multi_agent_roadmap.md` (executive) and `docs/roadmaps/multi_agent_one_page.md` (full).

## Recent Changes (Digest)

- Unified ASCII-only diagrams across briefs; removed Mermaid.
- Added Adoption Thresholds table (Reviewer/Parallelization/Async/PG index).
- Clarified baseline: acceptance-gated artifacts + Plan→Executor with deterministic ACI IO; async/parallel are optional.
- Added Manus Chinese keypoints mirror at `../context-engineering-manus/KEYPOINTS.zh.md`.

## Stability & Consistency

- Stable baseline: acceptance-gated artifacts; Plan→Executor (single-step) with deterministic ACI IO; context discipline; minimal tool governance; trace-first evaluation.
- Optional modules (enable by metrics): Reviewer/Critic; Parallelization/Synthesizer; Async executor; Postgres index for lineage/queries.
- Consistency rule: both `docs/roadmaps/multi_agent_roadmap.md` and `docs/roadmaps/multi_agent_one_page.md` must mirror these baselines and options (Required vs Optional) and reflect any threshold updates.

## Quick Links

- Claude Code: claude-code.md
- Manus (Context Engineering): manus.md
- SWE-agent (SWE-bench): swe-agent.md
- OpenDevin (Generalist dev agent): open-devin.md
- Voyager (Minecraft, skills/curriculum): voyager.md
- AutoGPT (autonomous loop baseline): autogpt.md
- AutoGen (multi-agent conversations): autogen.md
- GitHub Copilot (Agent mode / Coding agent): copilot-agent.md
- OpenAI Codex (historical foundation): openai-codex.md

## Comparison Matrix (At a Glance)

| Agent | Primary Domain | Core Loop / Architecture | Highlights | Risks / Limitations | What to Borrow |
| --- | --- | --- | --- | --- | --- |
| Claude Code | Agentic coding (CLI/web) | analyze → plan → edit → run → observe → repair; MCP tools; sandbox | Environment-driven context; artifact-first; permissions/safety | Learning curve; noisy context if undisciplined | Repo docs as context; artifact-first loops; minimal tool surface |
| Manus | Production agents | Stable prefixes; append-only logs; prefill/masking; FS as memory | KV-cache economics; keep failures; diversity of demos | Strict serialization discipline; provider support needed | Deterministic context; mask tools; recitation (todo) |
| SWE-agent | GitHub issues (SWE-bench) | LM-centric ACI; retrieve→patch→test; deterministic IO | Strong benchmark results; transparent ACI | Setup heavy; test quality sensitive | Deterministic tool IO; benchmark-first design |
| OpenDevin | Generalist dev agent | Sandbox (shell/browser/editor); plan→act→observe | Breadth of tools; open-source platform | Operational overhead; integration quality critical | Full-stack sandbox for eval; agent hub abstractions |
| Voyager | Embodied agent (Minecraft) | Auto-curriculum; skill library; iterative prompting | Reusable skills; rapid milestone unlocks | Domain-specific; skill governance | Skill library + self-verification patterns |
| AutoGPT | Autonomous loop baseline | plan→act→observe→reflect; vector memory | Popularized agent loops | Drift; weak grounding; eval issues | Keep scaffold but enforce acceptance artifacts |
| AutoGen | Multi-agent orchestration | Conversable agents; flexible patterns; no-code Studio | Broad interaction patterns; HIL | Token bloat risk; role ambiguity | Typed conversation patterns; interchangeable agents |
| Copilot Agent | Coding in editor/cloud | Agent mode (sync) + Coding agent (async/Actions) | Issue→PR integration; enterprise guardrails | Latency/quotas; black-box infra | Separate sync collaborator vs async background agent |
| OpenAI Codex | Historical code model | NL→code; completions | Seeded coding ecosystem | Not an agent; limited context | Treat models as engines behind stable protocols |

## Patterns We Adopt (Signals)

- Artifact-first loops (diffs/docs/logs) with acceptance checklists (Claude Code, SWE-agent, Copilot).
- Deterministic, append-only context with stable prefixes; KV-cache awareness (Manus).
- Minimal, LM-friendly tool interfaces (SWE-agent ACI; MCP discipline).
- Separate synchronous collaborator (in-editor) from asynchronous background agent (CI/Actions) (Copilot).
- Skill libraries and self-verification/recitation for longer horizons (Voyager, Manus).
- Conversation patterns as orchestration, not the product; keep token budgets tight (AutoGen).

## Key Conclusions (Prioritized & Orthogonal)

1) Acceptance‑gated artifacts (highest leverage).
   - Make diffs/docs/logs/tests the primary control surface. Decisions flow from artifacts and checklists, not chat. Improves auditability, rollback, and evaluation.

2) Plan → Executor with single‑step granularity + deterministic ACI IO.
   - Planner emits one actionable step and acceptance criteria; Executor performs exactly one step with typed, deterministic tool IO. Reduces token cost and failure surface; matches SWE‑agent evidence.

3) Context discipline and stability.
   - Append‑only transcripts, stable prefixes, deterministic serialization; prefer masking/prefill over tool list mutation. Preserves KV‑cache and reduces drift (per Manus).

4) Tooling governance with minimal surface.
   - MCP‑first, typed schemas, small IO. Fewer, stronger tools outperform broad, chatty toolsets; easier to secure and evaluate.

5) Trace‑first observability and evaluation.
   - High‑fidelity traces and multi‑dimensional scorecards with kill/switch criteria. Enables rapid iteration and safe rollbacks.

6) Extensibility modules are optional.
   - Async executor (parallel sandboxes) and parallelization/synthesizer improve throughput for batch/refactors; enable only when justified by backlog and metrics.

7) Reusable skills and externalized memory.
   - Encode SOPs as skills; keep long‑horizon knowledge in artifacts/files, not prompts. Reduces prompt bloat and improves reuse and transfer.

- Artifact-first, ACI-style IO is a prerequisite for reliability.
  - Deterministic tool IO (SWE-agent ACI) > chatty conversations; keeps token budgets tight and results reproducible.
  - PR/diff + logs + test results form the standard acceptance set across agents.

- Context discipline matters in production.
  - Manus shows KV-cache economics and the pain of cache breakage; we should keep append-only logs, stable prefixes, and prefer masking/prefill over dynamic tool removal.

- Full-stack sandboxes unlock realistic eval and parallel jobs.
  - OpenDevin and Copilot/Codex highlight shell+browser+editor or cloud runners with repo preloads and build/test loops; we can adopt a minimal version (local Docker or remote worker) for POC.

- Skill libraries help scale beyond one-off steps.
  - Voyager demonstrates reusing skills; we can encode SOP-like skills for demand/requirement creation to reduce prompt bloat and improve reuse.

## Adoption Guide (Scenario → Pattern)

| Scenario | Recommended Pattern | Notes |
| --- | --- | --- |
| Demand/Requirement Creation | Planner→Operator (sync), optional Reviewer | Artifacts: PRD.md, personas.md, acceptance_checklist.md |
| Repo Q&A / Small Fixes | Plan → Executor (sync); artifact-first diffs/tests | Keep ACI IO deterministic; enable quick PRs |
| Batch Fixes / Refactors | Async executor (extension) + Reviewer | Parallel sandboxes per task; merge via PR review |
| Research & Synthesis | Planner→Operator with evidence gating | Artifacts: notes.md, table.csv, citations.json |
| High-risk Changes | Add Reviewer/Critic + checklists | Risk-based enabling to control token/latency |

## Metric Targets (Initial)

- PR acceptance rate, time-to-first-diff, repair-loop count.
- KV-cache hit rate (where applicable), token cost per task, TTFT.
- Retriever quality (precision/recall@k) for coding agents with retrieval.
- Sandbox stability: build/test pass rates, latency p95.

## Evolution Recommendations

1) Start with Plan → Executor (sync) + artifact-first to cover requirement creation flows.
2) Add ACI-like constraints (typed, deterministic tool IO) and enforce acceptance checklists.
3) Build a small skill library (SOPs) for requirement structuring to reduce prompt bloat.
4) Strengthen observability: task success, repair loops, tool errors, cost/latency; define kill/switch criteria.
5) Introduce async executor (local Docker or thin remote worker) only when backlog/batch needs justify it.

## Adoption Thresholds (Crisp Gates)

| Capability | Default | Enable When | Metrics Gate |
| --- | --- | --- | --- |
| Reviewer/Critic | Off | High-risk domains or low-confidence outcomes | Non-compliance > threshold; confidence < gate |
| Parallelization | Off | Batch/refactor workloads benefit | Speedup ≥ 1.5× with acceptable cost |
| Async Executor | Off | Backlog requires background throughput | Queue wait time > SLO |
| Postgres Index | Off | Ad-hoc queries/lineage frequent | >100 queries/day; lineage joins needed |

## Roadmap Alignment

- Roadmaps: `../../roadmaps/multi_agent_roadmap.md` (executive) and `../../roadmaps/multi_agent_one_page.md` (full) consume this index. Alignment checkpoints:
  - Baseline = Required: Planner, Operator (ReAct), Task Board, Artifact Store.
  - Optional: Reviewer/Critic, Reflexion notes, Parallelization (ParallelAgent/Synthesizer), Async executor.
  - Rationale: acceptance-gated artifacts; Plan→Executor with deterministic ACI IO; context discipline; minimal tool governance; trace-first evaluation; skills/memory are reusable modules.
  - Any changes to Key Conclusions or Adoption Thresholds here must be reflected in the Roadmap’s Solution Brief, Core Patterns, and Implementation Plan.
  - Mapping reference in roadmap: section “Research ↔ Roadmap Mapping”.

## Open Questions

- What default thresholds should trigger Reviewer vs auto-repair?
- How to balance KV-cache stability with retrieval freshness and tool churn?
- Which domains benefit from skill libraries vs ad-hoc tools?

## References

See each brief for sources; additional survey content: ../taskboard_artifact_store_survey.md
