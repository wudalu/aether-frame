# Evaluation Pipeline and Dataset Strategy

Status: Draft
Objective: Define a trace-first evaluation pipeline (LangFuse) and a practical dataset strategy for both offline and online assessment of agent quality.

## Diagram (Pipeline — ASCII)

```
Context Pack
Collaboration Docs
Skills + MCP Docs
   \        |        /
        LangFuse Traces
        /            \
Offline Datasets   Online Experiments
        \            /
     Multi-dimensional Scorecard -> Design Updates
```

## Observability and Tracing

- LangFuse SDK: record traces, spans, tool calls, inputs/outputs, and custom scores.
- Map ADK session/events → trace tree; annotate nodes with role (Planner/Operator/Critic) and step IDs.
- Privacy: redact PII; attach artifacts by reference.

## Metrics

- Task success: boolean/graded success vs. acceptance criteria.
- Faithfulness/grounding: source coverage, hallucination checks on retrieved context.
- Trajectory quality: step count, repair loops, tool error rate.
- Efficiency: latency, tokens, cost.

## Multi-Dimensional Scorecard (Confirmed)

- Dimensions: (1) Quality/Success vs. acceptance criteria, (2) Grounding/Faithfulness, (3) Trajectory/Process quality, (4) Efficiency (latency/tokens/cost).
- Weighting: support scenario-based weights (e.g., reliability-first vs. cost-first). Keep weights in experiment config for reproducibility.
- Slicing: analyze by task type, tool usage, context size/budget, and model/provider versions to localize regressions.

Example scoreboard fields: `success@k`, `grounding_score`, `critique_agreement`, `steps`, `repairs`, `tool_error_rate`, `latency_p95`, `tokens_total`, `cost_per_task`.

## Offline Evaluation

- Datasets
  - Synthetic tasks with constraints (budgets, tool access), programmatic validators where possible.
  - Real task sampling from production traces (with anonymization and consent).
  - Multi-turn conversations that exercise planning, ReAct, and collaboration.
- Labeling
  - Gold answers via tests/validators (for code, SQL, retrieval QA).
  - LLM-as-judge with explicit rubrics for subjective outputs; spot-check with humans.
  - Pairwise preference (A/B) for qualitative comparisons.
- Execution
  - Use LangChain Evaluate on LangFuse datasets where applicable; export/import connectors.
  - Store run configs (model, temps, tools) for reproducibility.

## Online Evaluation

- Controlled A/B or interleaving on live traffic (non-critical paths first).
- Success proxies: user correction rate, retry rate, deflection, time-to-completion.
- Guardrails: rate limits and rollbacks on regressions.

## Score Analytics and Dashboards

- Distribution analysis, agreement between evaluators (LLM vs. human), regression detection.
- Slice by task type, context size, tool usage, and model versions.

## Data Management

- Version datasets; track consent and retention.
- Ensure reproducibility (fixed seeds, prompt versions, tool snapshots).

## ADK Integration Notes

- Thin tracing hooks in façades that forward to a tracing layer; keep façade logic minimal.
- Externalize evaluators and datasets in separate modules to avoid runtime bloat.

## References

- [LangFuse Cookbooks](https://langfuse.com/guides/cookbook) (LangGraph agents, LangChain evaluation, multi-turn evaluation, external pipelines).
- [LangFuse Blog: Evaluating Multi-Turn Conversations](https://langfuse.com/blog/2025-10-09-evaluating-multi-turn-conversations).
- [LangFuse Blog: Evaluating LLM Applications—A Comprehensive Roadmap](https://langfuse.com/blog/2025-11-12-evals).
- [LangSmith Docs: How to Evaluate Your Agent with Trajectory Evaluations](https://docs.langchain.com/langsmith/trajectory-evals).

## Research Inputs & Rationale

- **LangFuse cookbooks/blogs** advocate for N+1 evaluations, simulated conversations, and multi-dimensional scorecards; we follow that playbook to ensure trace-first instrumentation and rubric-based scoring.
- **LangSmith trajectory evaluations** provide patterns for step-level scoring, motivating our trajectory_score outline and the inclusion of repair/step counts.
- **Industry case studies** emphasize combining offline gold datasets with online experiments; hence our dual pipeline and rollback guardrails.

---

## Decisions & Trade-offs

- Trace-first: without high-fidelity traces and spans, evaluation is guesswork; instrument first.
- Multi-dimensional scoring: quality/grounding/process/efficiency; weights are scenario-specific.
- Combine gold and rubric: use tests/validators where possible; fallback to rubric-based LLM-as-judge with human spot checks.

## Applicability & Non-Applicability

- Applicable: agents with tool usage and multi-step flows; tasks where acceptance criteria can be stated.
- Caution: subjective creative tasks without rubrics; high-risk domains that require domain-expert evaluation.

## MVP → Enhanced Path

- MVP: LangFuse tracing, minimal dataset with programmatic validators (code/SQL), rubric prompts for others, basic scorecards.
- Enhanced: trajectory-level scoring, pairwise preference tests, simulated conversations, regression alarms and dashboards.

## Dataset Taxonomy

- Gold (programmatic): code generation/fix (unit tests), SQL (result equivalence), retrieval QA (exact/soft match).
- Rubric-scored: structured rubrics for relevance, coherence, safety; LLM-as-judge with agreement checks.
- Preference: A/B pairwise or interleaving; useful when no single gold exists.

## Rubric Prompt (Template)

```
You are an evaluator. Given the user goal, acceptance criteria, context snippets, and the agent's final answer, score the response.
Return a JSON with fields {"success":0-1, "grounding":0-1, "safety":0-1, "comments":"..."}.
Weigh acceptance criteria > grounding > style.
```

## Trajectory Evaluation (Outline)

- Inputs: step logs, tool calls, errors, repairs
- Signals: unnecessary steps, loops, tool errors, long tail latencies
- Output: trajectory_score, with breakdown by heuristics

## Online Experimentation

- A/B: split traffic on low-risk surfaces; monitor primary and guardrail metrics.
- Interleaving: alternate responses at inference; collect preferences.
- Rollback criteria: define strong thresholds for regressions.

## Open Questions

- Which domains to seed for P0 datasets (code fix, retrieval QA, tool orchestration)?
- What minimal sample size yields stable confidence per slice?
- How often should we refresh synthetic tasks?

## Task List (Planning Only)

- Define base metrics and dashboard layout
- Draft rubric bank per domain and acceptance templates
- Curate P0 datasets and collection pipelines
- Write experiment/rollback playbooks
