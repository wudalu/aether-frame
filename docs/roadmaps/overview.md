# Agent Evolution Overview (Refocused)

Status: Draft
Timeframe: 2026 H1–H2
Scope: Google ADK–based service; small-team multi-agent collaboration; context organization; skills/tools via MCP; evaluation + datasets.

This overview consolidates four focused research deliverables and extracts a cohesive plan prioritizing small-number agent collaboration (planning + ReAct), pragmatic context organization (prompt, tool, memory), skills–tool abstraction with MCP, and evaluation pipelines with dataset strategy.

- Multi-Agent Collaboration (few agents, strong protocols): see `multi_agent_roadmap.md`.
- Context Engineering (organize prompt/tool/memory + overflow handling): see `context_engineering_org.md`.
- Skills & Tools with MCP (abstractions and governance): see `skills_tools_mcp_abstraction.md`.
- Evaluation & Datasets (pipelines and data strategy): see `evaluation_pipeline_and_datasets.md`.

This plan supersedes any earlier general roadmaps by emphasizing fewer agents with clearer collaboration patterns.

## Key Tenets

- Fewer, better agents: Planner + (ReAct-capable) Operator + optional Critic/Judge. Avoid agent sprawl.
- Protocol over proliferation: clear roles, message schemas, turn-taking and arbitration; artifacts over chat.
- Context as a product: structure prompts, stage tools, and manage memory with explicit budgets and compression.
- Skills on top of tools: skills orchestrate toolchains; tools are atomic and MCP-first.
- Trace, evaluate, iterate: LangFuse-based tracing + offline/online eval loops, supported by curated datasets.

## Document Map & Cross-References

| Doc | Focus | Feeds / Consumes |
| --- | --- | --- |
| `multi_agent_roadmap.md` | Planner→Operator protocols, message schemas, acceptance checklists | Needs context packs + tool registry metadata |
| `context_engineering_org.md` | Prompt/Tool/Memory staging, budgets, overflow handling | Supplies structured context to Planner/Operator, evaluation traces |
| `skills_tools_mcp_abstraction.md` | Skill SOPs + MCP governance | Provides tool contracts to Operator/Reviewer; metrics feed evaluation |
| `evaluation_pipeline_and_datasets.md` | LangFuse tracing, scorecards, datasets | Consumes artifacts + governance data from other docs |

Reference paths between docs:

- Collaboration ↔ Context: message schema references the context pack layout (Section “Sectioned Prompt Template”).
- Collaboration ↔ Skills/MCP: Operator actions invoke Skills defined in `skills_tools_mcp_abstraction.md`.
- Context ↔ Evaluation: structured prompts and artifact links simplify LangFuse trace analysis.
- Skills/MCP ↔ Evaluation: tool registry metadata (side-effects, latency) maps to scorecard fields.

Use this table to navigate dependencies before implementation.

## Research Basis

- **ReAct / Reflexion / Planner–Executor studies** motivate the Planner→Operator baseline, cited throughout `multi_agent_roadmap.md`.
- **Context engineering field guides (LangChain, Manus, Kubiya, FlowHunt, iKala)** shape the prompt/selection/compression strategies captured in `context_engineering_org.md`.
- **Anthropic Skills + MCP ecosystem analyses (IntuitionLabs, Skywork, Gend, Milvus)** inform the Skill vs MCP layering in `skills_tools_mcp_abstraction.md`.
- **LangFuse & LangSmith evaluation cookbooks** justify the multi-dimensional scorecard and dataset plan in `evaluation_pipeline_and_datasets.md`.

Each sub-document details how these external signals influence its recommendations and how we tailor them to ADK constraints.

## Decisions (Confirmed)

- Default collaboration pattern: Planner → Operator (ReAct) with optional Critic/Reviewer and Reflexion-style self-feedback loops. Tree-of-Thoughts/tree search remains optional for high-accuracy discriminator scenarios only.
- Evaluation is multi-dimensional: measure quality/success vs. acceptance criteria, grounding/faithfulness, trajectory/process quality, and efficiency (latency/tokens/cost). Dashboards should allow reweighting and slicing by task type and context size.

## Immediate Actions (Q2)

- Add collaboration protocol scaffolds (roles, schemas, turn policy) integrated with ADK session service.
- Introduce context organization policies and a minimal budget/compression utility.
- Define `Skill`/`Tool` abstractions and MCP client shim; enumerate candidate MCP servers.
- Start LangFuse tracing and build a seed dataset for offline evaluation.

## Milestones & Dependencies

- Phase 1 (Weeks 1–2):
  - Collaboration protocol (Planner→Operator baseline), acceptance checklists, artifact conventions
  - Context templates + budget presets; hybrid retrieval with MMR guidance
  - Skill/Tool abstraction draft; MCP shortlist
  - Tracing hooks design + initial datasets definition

- Phase 2 (Weeks 3–4):
  - Optional Reviewer/Reflexion loops defined
  - Overflow handling algorithms and example prompts published
  - Governance policies for tools (side-effects, quotas, masking)
  - Scorecard schema + rubric bank; offline eval dry-run plan

- Phase 3 (Weeks 5–6):
  - Finalize documentation with case studies and SOPs
  - Prepare execution backlog (ADRs/Issues) — implementation phase to be decided later

Dependencies:
- Collaboration protocol depends on context templates and acceptance criteria
- Evaluation relies on tracing design and artifact conventions
- Skill/Tool governance depends on registry schema

## Acceptance Criteria (Planning Stage)

- All four sub-documents completed with Decisions & Trade-offs, Applicability, MVP→Enhanced, Open Questions, Task List
- References to at least two independent sources per critical claim
- Overview links and milestone plan coherent and actionable

## References (selected)

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) (ICLR 2023).
- [Claude Code: Best Practices for Agentic Coding](https://www.anthropic.com/engineering/claude-code-best-practices) (Anthropic, 2025-04-18).
- [Navigating Modern LLM Agent Architectures](https://www.wollenlabs.com/blog-posts/navigating-modern-llm-agent-architectures-multi-agents-plan-and-execute-rewoo-tree-of-thoughts-and-react) (Wollen Labs, 2025-07-17).
- [Context Engineering for AI Agents: Lessons from Building Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus) (2025-07-18).
- [LangFuse Cookbooks & Guides](https://langfuse.com/guides/cookbook) (LangGraph agents, LangChain evaluation, multi-turn conversations).
