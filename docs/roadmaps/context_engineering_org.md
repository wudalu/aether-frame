# Context Engineering: Organizing Prompt, Tools, and Memory

Status: Draft
Objective: Research-backed guidance to structure context (prompt + tools + memory) and handle overflow through selective inclusion, compression, and extraction.

## Diagram (Layered Context — ASCII)

```
Instruction -> Task -> Tools -> Evidence -> Memory -> Conversation -> Slack

Side docs:
- Instruction -- Collaboration Doc
- Tools       -- Skills + MCP Doc
- Evidence    -- Artifact Store (see `multi_agent_roadmap.md`)
- Memory      -- Evaluation Doc
```

Flow:
- Instructional layer informs Planner/Operator prompts (see `multi_agent_roadmap.md`).
- Task layer derives from Planner plan steps; also used in acceptance checklists.
- Tool layer references schemas defined in `skills_tools_mcp_abstraction.md`.
- Evidence layer carries summaries + URIs to Artifact Store outputs; raw tool outputs stay out of prompt.
- Memory layer feeds both collaboration (working notes) and evaluation (artifact links) in `evaluation_pipeline_and_datasets.md`.
- Conversation layer holds the most recent turns for immediacy.
- Slack (token buffer) ensures safe margins for model responses.

## Context Layers and Ordering

1) Instructional layer
- Stable role, safety, constraints, and objectives; minimal and composable.

2) Task layer
- Current goal, acceptance criteria, plan step, and constraints (budget, latency, risk).

3) Tool layer
- Only tools relevant to the current step. Include: name, purpose, IO schema, constraints, example calls.

4) Memory/knowledge layer
- Working memory: recent turns and step-specific notes.
- Knowledge: retrieved documents/snippets relevant to this step.

5) Slack layer
- Reserved output buffer so the model can respond without truncation; also absorbs tool-result expansion.

### Layer Order (ASCII)

```
Most stable
  |
  v
+-------------------------+
| System / Instruction    |
+-------------------------+
            |
            v
+-------------------------+
| Task / Step / Checklist |
+-------------------------+
            |
            v
+-------------------------+
| Tools (step-only)       |
+-------------------------+
            |
            v
+-------------------------+
| Evidence                |
| (summary + artifact://) |
+-------------------------+
            |
            v
+-------------------------+
| Memory (Top-K, time)    |
+-------------------------+
            |
            v
+-------------------------+
| Conversation Tail       |
| (last-N turns)          |
+-------------------------+
            |
            v
+-------------------------+
| Slack (output buffer)   |
+-------------------------+
            |
            v
Most dynamic
```

Note: these "layers" map to different fields in the outgoing LLM request:
- System/Instruction -> `config.system_instruction`
- Tools -> `tools_dict`
- Task/Evidence/Memory (+ user request) -> Pack Payload text in the final user message (`contents[]`)
- Conversation Tail -> recent turns in `contents[]`

Context Pack = the full outgoing LLM request object: `system_instruction + contents[] + tools_dict`.

## Key Concepts (Definitions + Examples)

| Concept | Definition | Example |
| --- | --- | --- |
| Context Pack | Step-scoped final LLM request (system + messages + tools), budgeted and replayable | `system_instruction + contents[] + tools_dict` (tracked by `pack_id`, with `artifact://.../manifest.json`) |
| Pack Payload | The structured text we render and place into the final user message (the pack "payload") | `CONTEXT PACK\nTASK:...\nEVIDENCE:...` |
| Manifest | Metadata for replay/audit of a pack | `manifest.json` with budgets + drops |
| Step | Atomic unit of work from the plan | “Summarize 3 competitor reports” |
| Acceptance checklist | Criteria that define “done” | “Include sources + risks + gaps” |
| Evidence | Proof artifacts referenced in prompt | `artifact://tasks/123/step-2/report.md` |
| Memory (working) | Short-term notes for current step | “Key constraints: budget, tone” |
| Memory (long-term) | Cross-session durable knowledge | “User prefers concise output” |
| Conversation tail | Most recent turns kept verbatim | Last 3 user/agent exchanges |
| Slack | Reserved output buffer | Keep 10–15% window for reply |
| Tools (step-only) | Only tools required for this step | For “doc analysis”: `file_read`, `search` |
| Truncation event | Logged drop/compress decision | `{"layer":"memory","reason":"overflow"}` |
| Task Board | Step scheduler and state | `ready -> claimed -> done` |
| Artifact Store | Evidence storage with stable URIs | `artifact://...` |

Relationship (ASCII):

```
+-------------------------------------------------------------+
| Context Pack (final LLM request for ONE call; step-scoped)   |
|                                                             |
|  system_instruction (stable)                                |
|  +---------------------+                                    |
|  | <role/safety/rules>  |                                    |
|  +---------------------+                                    |
|                                                             |
|  tools_dict (step-only)                                     |
|  +---------------------+                                    |
|  | tool schemas...      |                                    |
|  +---------------------+                                    |
|                                                             |
|  contents[] (messages)                                      |
|  +---------------------+                                    |
|  | ...conversation tail |  (prior user/model turns)          |
|  | user message (final) |---> Pack Payload (structured text) |
|  +---------------------+                                    |
+-------------------------------------------------------------+

Manifest (artifact; follows Artifact Store strategy)
  artifact://.../manifest.json
```

Relationship (Table):

| Item | Type | Lives in | Seen by LLM? | Purpose |
| --- | --- | --- | --- | --- |
| Context Pack | Request object | `LlmRequest` (runtime; optionally logged/snapshotted) | Yes | The actual input for one model call |
| Pack Payload | Text string | `contents[]` final user message `parts[].text` | Yes | Make TASK/STEP/EVIDENCE/MEMORY explicit |
| Manifest | JSON file | Artifact Store (`artifact://.../manifest.json`) | No (by default) | Replay/audit: budgets, drops, sources, URIs |

## Selection and Compression Policies

- Relevance-first selection: Hybrid retrieval (BM25 + vector) with MMR re-ranking to pick top-k snippets.
- Query expansion (optional): multi-query or HyDE to improve recall on ambiguous intents.
- Budget-aware trimming: token accounting; prefer structured summaries (bullets, key-value) over raw transcripts.
- Aging policy: demote older turns to summaries; keep entity/state tables in structured form.
- Tool results: summarize with provenance; store raw outputs as artifacts.

## Prompt Structuring Guidelines

- Use explicit section headers: ROLE, GOAL, STEP, CONSTRAINTS, TOOLS (schemas), EVIDENCE, MEMORY.
- Keep the header format stable across turns. The model learns the schema; frequent reformatting hurts reliability.
- Put the Pack Payload in the final user message and embed the original user request verbatim. Do not duplicate the conversation tail inside the Pack Payload.
- Keep system_instruction stable, but explicitly tell the model to treat TASK/STEP/ACCEPTANCE in the Pack Payload as authoritative for the current step.
- Keep tool schemas short and typed; omit non-relevant tools entirely.
- Require “what-to-do-next” and “stop conditions” to reduce drift.
- Encode acceptance criteria as a checklist; Critic reuses the same list.

Contract placement options:

Option A (system_instruction; stable and minimal):

```
You will receive a CONTEXT PACK in the final user message.

Rules:
- Treat TASK/STEP/ACCEPTANCE in the pack as authoritative for the current step.
- Use EVIDENCE links (artifact:// URIs) to justify claims; do not fabricate.
- If evidence is missing, say "unknown" and request the needed tool/action.
- Use only the provided tools; do not assume hidden tools exist.
```

Option B (Pack Payload header; avoid changing system_instruction):

```
INTERPRETATION RULES:
- Follow TASK/STEP/ACCEPTANCE below.
- Cite EVIDENCE (artifact:// URIs); do not fabricate.
- If evidence is missing, say "unknown" and request tools.
```

LLM comprehension guardrails:
- Keep Pack Payload short (bullets, not raw dumps). Prefer evidence URIs over pasted tool output.
- Put the most important items near the end of the Pack Payload (Acceptance + User Request + top evidence), not in the middle.
- Optional "recitation": first restate STEP + ACCEPTANCE in 1-2 lines before producing the final output.
- Acceptance gating: if output fails the checklist, run a repair pass with the missing checklist items highlighted.
- Avoid conflicting instructions across system_instruction vs Pack Payload; one schema, stable headers.

## Context Pack Manifest (Trace-First, Multi-Agent Aligned)

We treat each prompt as a deterministic Context Pack with a manifest stored in the Artifact Store. This aligns with the multi-agent roadmap’s acceptance-gated artifacts and append-only traces.

- Deterministic assembly per Task Board step: `task_id`, `step_id`, checklist, tool scope, evidence URIs, memory snippets, and last-N turns.
- Stable ordering: `System -> Task -> Tools -> Evidence -> Memory -> Conversation -> Slack`.
- Evidence-only rule: tools write raw outputs to Artifact Store; prompt only carries summaries + `artifact://` URIs.
- Manifest fields: `pack_id`, `model`, `window`, `layer_budgets`, `truncation_events`, `artifact_uris`, `checksum`.
- Tool scope stability: avoid dynamic add/remove when possible; gate tool choice with scopes (aligns with Manus-style action control).

Why this structure is reasonable (industry pattern):
- Stable system prefix + dynamic user message context is a common RAG/agent pattern (better caching and fewer behavior regressions).
- Explicit section headers (TASK/STEP/ACCEPTANCE/EVIDENCE/MEMORY) reduce ambiguity vs free-form chat.
- Evidence-as-URIs + artifacts (instead of pasting raw tool output) is common for auditability and long contexts.
- A manifest/audit record is standard practice for replay and debugging in production agent systems.

Manifest = the audit receipt for a Context Pack. It records how the pack was built so we can replay, debug, and tune it. It follows the same storage strategy as the Artifact Store (dev: FS, prod: object storage).

Example `manifest.json` (abridged):

```
{
  "pack_id": "pack_2026-01-28T10:20Z_task_42_step_3",
  "model": "gpt-4.1",
  "window": "128k",
  "layer_budgets": {
    "system": "6%",
    "task": "8%",
    "tools": "5%",
    "evidence": "50%",
    "memory": "22%",
    "conversation": "9%",
    "slack_min": "10%"
  },
  "artifact_uris": [
    "artifact://tasks/42/step-3/report.md",
    "artifact://tasks/42/step-3/source_index.json"
  ],
  "truncation_events": [
    {"layer": "memory", "reason": "overflow", "dropped_ids": ["mem_17", "mem_22"]}
  ],
  "checksum": "sha256:..."
}
```

### Context Pack Assembly (ASCII)

```
Task Board (step) -----> Pack Builder -----> Context Pack -----> Model
       |                     |                    |
       |                     |                    v
       |                     |              Response + Evidence
       |                     v                    |
       |               manifest.json               v
       |                     |              Artifact Store
       v                     |
Checklist/Constraints -------+

Tools -> raw outputs -> Artifact Store
                   -> Evidence summaries -> Context Pack (EVIDENCE layer)
```

### Manifest Fields (Table)

| Field | Purpose | Example |
| --- | --- | --- |
| `pack_id` | Deterministic pack identifier | `pack_2026-01-27T12:00Z_step_3` |
| `model` | Model name/version | `gpt-4.1` |
| `window` | Context window size | `128k` |
| `layer_budgets` | Per-layer token caps | `{system: 6%, task: 8%, ...}` |
| `truncation_events` | What was dropped + why | `[{layer: "memory", reason: "overflow"}]` |
| `artifact_uris` | Evidence references | `artifact://tasks/123/step-3/...` |
| `checksum` | Replay integrity | `sha256:...` |

## Overflow Handling Algorithm (Sketch)

Following the write/select/compress/isolate guidance from LangChain’s Context Engineering blog and Manus’s context playbook:

1) Compute token budget and candidate context set (task, tools, evidence, memory, conversation).
2) Select essential items by priority: (a) acceptance criteria, (b) current step, (c) evidence for checklist items, (d) top-k memory/retrieval, (e) recent turns.
3) If overflow, compress in order: (i) memory → summary, (ii) older evidence → summary, (iii) trim tool examples, (iv) tighten step summary.
4) If still overflow, deterministically drop by score: Memory -> older Evidence -> older Conversation.
5) Emit final Context Pack and persist `manifest.json` with truncation events and dropped IDs.

### Overflow Flow (ASCII)

```
Start
  |
  v
Compute budgets + candidates
  |
  v
Select essentials (acceptance, step, evidence, memory, turns)
  |
  v
Tokens <= budget?
  | yes -------------------------------> Emit Pack + manifest.json
  |
  no
  |
  v
Compress in order:
  1) Memory -> summary
  2) Older Evidence -> summary
  3) Trim tool examples
  4) Tighten step summary
  |
  v
Tokens <= budget?
  | yes -------------------------------> Emit Pack + manifest.json
  |
  no
  |
  v
Deterministic drop:
  Memory -> older Evidence -> older Conversation
  |
  v
Emit Pack + manifest.json (with truncation log)
```

### Required vs Optional Items (Table)

| Item | Required? | When Required | If Missing |
| --- | --- | --- | --- |
| Acceptance (checklist) | Yes | Always per step | Mark pack invalid; split/clarify step |
| Step (current task step) | Yes | Always per step | Mark pack invalid; request Planner to restate |
| Evidence | Conditional | When checklist requires proof or tools used | Keep empty; add `evidence_needed` in manifest |
| Memory | Optional | When retrieval hit rate or similarity exceeds threshold | Empty layer is acceptable |
| Conversation (turns) | Optional | Multi‑turn sessions; keep last‑N | Empty on first turn is acceptable |

### Truncation Order (Table)

| Priority | Layer | Rule | Rationale |
| --- | --- | --- | --- |
| 1 | Memory | Drop lowest score first | Avoid outdated/low-signal items |
| 2 | Evidence | Drop oldest, lowest checklist coverage | Preserve critical evidence |
| 3 | Conversation | Drop oldest turns | Keep immediacy |
| N/A | System/Task/Tools | Never truncate | Deterministic constraints |

## Memory Design

- Working memory: short-term notes per step with TTL; checkpoint after step completion.
- Long-term memory: entity and decision logs; promote salience via explicit writes.
- Artifact store: files, diffs, query results; referenced in prompts by IDs/paths, not inlined unless necessary.

### ADK Session & Memory Integration

- Map each layer to ADK `context.state`: instructions/task metadata live under `state.plan`, tool selections under `state.tools`, retrieval/memory under `state.knowledge`. `src/aether_frame/agents/adk/adk_agent_hooks.py` already loads/saves this state – extend it instead of reinventing storage.
- Use ADK’s Session Service plus memory preload utilities (see References) to hydrate working memory before every Planner/Operator turn. This covers the “write” and “select” steps automatically and lets compression focus on history/retrieval.
- Align Redis session service keys with ADK session IDs so Sequential/Parallel agents (and the Evaluator) can recover the same context mid-run.
- Persist artifact URIs through ADK ArtifactService (GCS/InMemory) and mirror them into `aether_frame.observability` for evaluation traceability.

## ADK Integration Notes

- Reuse Session Service for event history; add light helpers for token budgeting and summaries.
- Avoid heavy frameworks; favor small utilities (retriever, summarizer, budgeter) behind clean interfaces.

## ADK InvocationContext Alignment

We align Context Pack assembly with ADK’s InvocationContext so the pack is deterministic and traceable.

Important: InvocationContext is a runtime object built by ADK. The LLM does NOT read InvocationContext directly; it only sees a serialized LLM request (system + messages + tools). We do not replace ADK’s InvocationContext. Instead, our packer reads the InvocationContext (as ingredients) and renders a deterministic Context Pack into the final LLM request as structured text so the model can interpret each layer.

In short:
- ADK builds InvocationContext (session, memory, tools, state).
- aether-frame builds Context Pack (select/compress + manifest) from it.
- We rewrite the outgoing LLM request to match the Context Pack (before_model hook). Avoid "double context" by replacing, not stacking.

### Responsibility Split (Table)

| Concern | ADK (builds InvocationContext) | aether-frame (Context Engineering) |
| --- | --- | --- |
| Session events/history | Owns storage + retrieval (SessionService) | Select last-N turns + summarize older |
| Memory retrieval | Owns memory API + hits (MemoryService) | Rank/trim Top-K; add timestamps; decide when to include |
| Tool wiring | Owns tool runtime + schemas | Enforce step-only tool scope; stable ordering; log tool policy |
| Prompt assembly | Produces initial LLM request | Renders the final Context Pack sections + budgets |
| Overflow handling | Not opinionated | Select/compress/drop with deterministic rules |
| Audit/replay | Provides callbacks | Emits `manifest.json` + artifact URIs (Artifact Store strategy) |

### InvocationContext Flow (ASCII)

```
User Input
  |
  v
Runner -> ADK SessionService + MemoryService
  |
  v
InvocationContext (session events, memory hits, tool list, state)
  |
  v
Pack Builder + Task Board Step + Artifact URIs
  |
  v
Context Pack -> Model -> Response
```

### Where Pack Content Comes From (Table)

This table is a "source mapping": it describes where each pack layer's content is sourced from. It does NOT mean we convert the pack back into InvocationContext.

| Source | Pack Layer | Notes |
| --- | --- | --- |
| System prompt (agent config) | System | Stable prefix, cached |
| Task Board step + checklist | Task | Acceptance-gated |
| TaskRequest.available_tools | Tools | Step-only scope |
| Session events/history | Conversation | Last-N turns |
| MemoryService search hits | Memory | Top‑K + timestamps |
| Artifact Store URIs | Evidence | Summaries only |

Hooks: use `before_agent`/`before_model` to log the final Context Pack + `manifest.json` and correlate with `aether-frame.log`/CloudWatch.

### Injection Point (ASCII)

```
ADK builds InvocationContext
  |
  v
ADK renders initial LlmRequest (system + messages + tools)
  |
  v
before_model hook (aether-frame)
  - select/compress/isolate
  - enforce step-only tool list
  - rewrite the LlmRequest so it matches the Context Pack (messages + tools; keep system stable)
  - attach manifest URI to logs
  |
  v
Final LlmRequest -> model
```

### How Pack Payload Injection Works (ADK)

In ADK the outbound request is a `LlmRequest` with:
- `config.system_instruction` (system)
- `contents[]` (messages; `role=user|model`, `parts[].text`, etc.)
- `tools_dict` (tool schemas)

To make the Context Pack the final LLM input (without stacking "extra context"), we modify `llm_request.contents` in the `before_model` callback:
- Keep/trim the existing conversation tail (from `llm_request.contents`).
- Rewrite the current user message into a single "Context Pack" message that includes:
  - the original user request (verbatim)
  - the step + checklist
  - evidence summaries + artifact URIs
  - memory bullets (if any)
- Do not duplicate the conversation tail inside the Pack Payload; keep the tail as prior messages in `contents[]`. If the tail is truncated, include a short conversation summary inside the Pack Payload instead.
- Replace `llm_request.tools_dict` with the step-only tool subset.

Code sketch (conceptual):

```python
from google.genai import types

def before_model(callback_context, llm_request):
    # 1) Read the original user request from the last user message.
    user_text = extract_last_user_text(llm_request.contents)

    # 2) Build pack text from InvocationContext ingredients + step/checklist + artifacts,
    # and embed the original user request inside the pack.
    pack_text = render_context_pack_text(user_text=user_text, ...)

    # 3) Keep only last-N turns (conversation tail).
    llm_request.contents = keep_last_n_conversation(llm_request.contents, n=5)

    # 4) Rewrite the last user message so the final user message contains the Pack Payload.
    # (If multimodal parts exist, keep non-text parts and add the pack as a text part.)
    llm_request.contents = rewrite_last_user_message(llm_request.contents, pack_text)

    # 5) Enforce step-only tool scope.
    llm_request.tools_dict = step_only_tools_dict(...)
    return None
```

### Where Each Layer Lands in the LLM Request (Table)

| Context Pack Layer | Where it lands | Typical encoding |
| --- | --- | --- |
| System | System instruction | Stable prefix text |
| Task / Step / Checklist | Pack Payload (final user message) | Section headers (TASK/STEP/ACCEPTANCE) |
| Tools (step-only) | Tool schema list | Typed tool defs; scoped list |
| Evidence | Pack Payload (final user message) | Summary + `artifact://` URIs |
| Memory | Pack Payload (final user message) | Top-K bullets + timestamps |
| Conversation Tail | Messages list | Last-N turns verbatim |
| Slack | Not sent as text | Reserved budget in allocator + manifest |

### InvocationContext -> LLM Request (ASCII)

```
InvocationContext
  |-- system_prompt --------------> system message
  |-- tools ----------------------> tool schema list
  |-- session events -------------+-> messages[] (conversation tail)
  |-- memory hits ----------------+-> pack body (MEMORY section)
  |-- evidence URIs --------------+-> pack body (EVIDENCE section)
  |-- task step + checklist ------+-> pack body (TASK section)
                                  |
                                  v
                          serialized LLM request
```

### Pack Serialization Example (Excerpt)

```
ROLE:
- You are the Operator executing step 3.

GOAL:
- Summarize competitor analysis with sources.

STEP:
- Extract top 5 differentiators.
- Provide risks and gaps.

CONSTRAINTS:
- Latency <= 8s; cost <= $0.20
- Acceptance: include sources + evidence links

TOOLS (step-only):
- search_web(query, max_results)
- file_read(path)

EVIDENCE:
- artifact://tasks/42/step-3/report.md (summary: ...)
- artifact://tasks/42/step-3/source_index.json

MEMORY:
- User prefers concise output (2026-01-20)

USER REQUEST (VERBATIM):
- ...original user request text...

CONVERSATION TAIL:
- (omitted here; kept as prior messages in `contents[]` to avoid duplication)
- If the conversation tail is truncated, include a short CONVERSATION SUMMARY here instead.
```

This serialization is what the model actually reads; the “layers” are made explicit via headers, so the LLM can follow the structure.

### How Pack Links Back to ADK State and Events

ADK keeps two important internal sources of truth:
- `SessionService` events: the authoritative conversation timeline (user/model/tool events).
- `InvocationContext.state`: structured state for plan/tools/knowledge and other runtime metadata.

Our Context Pack does not replace these. It is a step-scoped projection built from them, then rendered into the outgoing `LlmRequest`.

ASCII overview:

```
SessionService events -------------------------------> conversation tail (last-N) --> LlmRequest.contents[]
InvocationContext.state (plan/tools/knowledge/...) --> select+compress -----------> Context Pack text ----+
Artifact Store (evidence + manifest) ---------------> summary + artifact:// URIs ----------------------->|
                                                                                                       v
                                                                                       rewrite last user message
                                                                                               (pack + user req)
```

Mapping table:

| ADK source | Where it lives | How we use it | What the LLM sees | How we correlate |
| --- | --- | --- | --- | --- |
| Session events/history | SessionService | Keep last-N turns; summarize older if needed | `contents[]` conversation tail | `session_id` + event ordering |
| `state.plan` | InvocationContext.state | Step + checklist + constraints | `TASK/STEP/ACCEPTANCE` sections | `task_id`, `step_id` |
| `state.tools` + TaskRequest tools | InvocationContext.state + request | Step-only tool scope | `tools_dict` (schemas) | `step_id` + tool names |
| MemoryService hits | MemoryService | Rank/trim Top-K; add timestamps | `MEMORY` section (bullets) | memory IDs + timestamps |
| Artifact Store URIs | Artifact Store | Evidence summaries + URIs | `EVIDENCE` section | `artifact://` URIs |
| Pack manifest | Artifact Store | Replay/audit of pack build | (not "seen") | `manifest.json` via `pack_id` |

Concrete (simplified) shape of the final LLM request:

```
system_instruction:
  "<stable agent instruction>"

contents:
  - role: user
    parts: [{text: "<older user turn>"}]
  - role: model
    parts: [{text: "<older assistant turn>"}]
  - role: user
    parts:
      - text: |
          CONTEXT PACK
          TASK: ...
          STEP: ...
          ACCEPTANCE: ...
          EVIDENCE: artifact://...
          MEMORY: ...
          USER REQUEST:
          <original user request verbatim>

tools_dict:
  <step-only tool schemas>
```

## Window-Proportional Budgeting (Dynamic Allocator)

Industry practice favors stable prefixes (for caching) and dynamic tails (for task variability). We implement a dynamic allocator that scales with the model’s context window and adapts to task signals.

1) Define floors: `System`, `Task`, `Tools`, `Slack_min` (fixed).
2) Compute remainder: `R = window - floors`. If `R < 0`, split the step.
3) Allocate remainder with weights:
   - `wE` (Evidence) = base + checklist_evidence_ratio + expected_tool_calls + risk_weight
   - `wM` (Memory) = base + retrieval_hit_rate + similarity + freshness
   - `wC` (Conversation) = base + unresolved_questions + dialogue_depth
4) Normalize: `allocX = R * wX / (wE + wM + wC)`.
5) Record budgets + signals in `manifest.json` for replay and tuning.

This respects Lost-in-the-Middle findings by keeping critical evidence near the end, and maximizes prompt caching by keeping the prefix stable.

### Allocator Signals (Table)

| Signal | Used In | Meaning | Example |
| --- | --- | --- | --- |
| `checklist_evidence_ratio` | Evidence | % checklist items needing evidence | 0.7 |
| `expected_tool_calls` | Evidence | Anticipated tool usage | 3 |
| `risk_weight` | Evidence | Compliance risk/impact | High |
| `retrieval_hit_rate` | Memory | Recent retrieval precision | 0.6 |
| `similarity` | Memory | Query-match score | 0.82 |
| `freshness` | Memory | Time decay | 2 days |
| `unresolved_questions` | Conversation | Open items to clarify | 4 |
| `dialogue_depth` | Conversation | Turns in current thread | 7 |

## References

- [LangChain Blog: Context Engineering for Agents](https://blog.langchain.com/context-engineering-for-agents/) (2025-07-02).
- [Kubiya: Context Engineering Best Practices for Reliable AI Performance in 2025](https://www.kubiya.ai/blog/context-engineering-best-practices).
- [FlowHunt: Context Engineering—The Definitive 2025 Guide](https://www.flowhunt.io/blog/context-engineering/).
- [iKala: Context Engineering—Techniques, Tools, and Implementation](https://ikala.ai/blog/ai-trends/context-engineering-techniques-tools-and-implementation/).
- [Manus: Context Engineering for AI Agents](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus).
- [Lost in the Middle (TACL 2024)](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long).
- [OpenAI Prompt Caching Guide](https://platform.openai.com/docs/guides/prompt-caching).
- [OpenAI Agents SDK: Context Management](https://openai.github.io/openai-agents-js/guides/context).
- [Anthropic Prompt Caching](https://docs.anthropic.com/de/docs/build-with-claude/prompt-caching).

## Research Inputs & Rationale

- **LangChain Context Engineering series** formalizes the write/select/compress/isolate pattern; we mirror that structure and map token budgets accordingly.
- **Kubiya / FlowHunt / iKala** articles stress hybrid retrieval + structured summaries to avoid “token rot”; this drives our priority ordering (acceptance → step → retrieval) and overflow algorithm.
- **Manus engineering notes** stress stable tool surfaces, deterministic serialization, and keeping errors in context; we reuse those to keep Planner/Operator prompts deterministic and trace-first.
- **Lost in the Middle** shows models attend best to beginning/end of long contexts; we place critical evidence near the end and keep stable prefixes for cache efficiency.
- **OpenAI/Anthropic prompt caching docs** justify stable prefixes and controlled tool lists for latency/cost benefits.

---

## Decisions & Trade-offs

- Token budget is first-class: we enforce explicit budgets per step and allocate to instructions > task > tools > memory/knowledge.
- Select then compress: avoid compressing everything; first choose essential pieces, then compress if still overflowing.
- Keep schemas out of prompt: tool schemas live in a registry; prompts only reference minimal metadata and the step’s selected tool(s).

## Applicability & Non-Applicability

- Applicable: RAG-style tasks, code/data workflows with tool usage, multi-turn assistance with clear goals.
- Caution: fully generative creative tasks without structure (compression may harm nuance); highly confidential data (ensure redaction/masking before retrieval).

## MVP → Enhanced Path

- MVP: fixed token budget thresholds, hybrid retrieval (BM25+vector) + MMR, conversation summarizer, artifact linking.
- Enhanced: optional multi-query/HyDE, cross-encoder re-ranking, semantic cache with guard conditions, entity/decision tables.

## Budget Floors + Task Profiles (Example)

### Floors (Fixed)

| Layer | Floor (Window %) | Note |
| --- | --- | --- |
| System | 6–8% | Stable prefix |
| Task + checklist | 6–10% | Acceptance constraints |
| Tools (step-only) | 4–6% | Minimal schemas |
| Slack_min | 10–15% | Output buffer |

### Task Profiles (Remainder Allocation)

| Profile | Evidence | Memory | Conversation |
| --- | --- | --- | --- |
| Research/Market analysis | 55–65% | 20–25% | 10–15% |
| Requirements/Docs | 45–55% | 25–30% | 15–20% |
| Test case construction | 50–60% | 20–25% | 10–15% |

## Overflow Algorithm (Pseudocode)

```
candidates = {instructions, step, acceptance, tools[minimal], evidence_summaries, memory_topk, conversation_tail}
pack = prioritize([acceptance, step, instructions, evidence_summaries, memory_topk, conversation_tail, tools])
while tokens(pack) > budget:
  if has(memory_long): collapse_to_summary()
  elif has(evidence_long): query_focused_summary()
  elif has(tool_examples): trim_examples()
  else: tighten_step_summary()
emit(pack); attach(artifact_links); log_truncation(manifest)
```

## Sectioned Prompt Template (Excerpt)

```
ROLE:
- You are the Operator executing step {n} of a plan.

GOAL:
- {goal}

STEP:
- {current_step}

CONSTRAINTS:
- token_budget={budget}, latency_target={latency}
- acceptance={checklist}

TOOLS (current step only):
- {tool_name}: {purpose}, inputs={typed}, outputs={typed}

EVIDENCE/MEMORY:
- recent_notes: {bullets}
- retrieved_snippets: {topk}
```

## Open Questions

- What default k and diversity should MMR use across domains?
- When should HyDE be enabled vs disabled?
- How strict should redaction/masking be for PII in retrieval logs?

## Task List (Planning Only)

- Define budget presets (quality-first vs cost-first)
- Write prompt templates per role (Planner/Operator/Reviewer)
- Document retrieval adapters and ranking knobs
- Specify artifact storage policy and retention windows
