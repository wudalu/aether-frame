# Agent Session Memory and Retrieval Best Practices

Date: 2026-03-24
Status: Draft

## Goal

Summarize current best practices for short-term memory, session-level retrieval, and context slicing in agent systems, with emphasis on official OpenAI and Anthropic guidance. This note is intended to inform Aether Frame's session lifecycle, context engineering, and future memory abstractions.

## Executive Summary

The current industry direction is not "put the whole conversation into the prompt." Strong production systems split memory into layers:

1. A hot conversation tail kept verbatim for immediate local coherence.
2. A compressed session summary or compaction artifact for older but still relevant history.
3. Structured session state for facts that should survive trimming.
4. Long-term memory or retrieval stores that are queried just in time rather than preloaded.

The most stable pattern is a hybrid:

- Keep the last `N` complete turns verbatim.
- Compress or compact older context.
- Extract stable facts into structured state or memory notes.
- Retrieve additional memory or knowledge only when the current step needs it.

OpenAI and Anthropic both now emphasize context curation over raw context size. Anthropic explicitly frames context as a finite resource with diminishing returns; OpenAI's latest APIs and cookbooks expose explicit conversation state, compaction, and retrieval primitives to support that same operating model.

## Working Taxonomy

### 1. Conversation state

The request chain or durable conversation object that preserves turn order and tool history.

- OpenAI: `conversation` objects or `previous_response_id` in the Responses API.
- Anthropic: session history managed by the API or SDK.

### 2. Short-term memory

Session-scoped context required for the current work item.

- Recent user asks
- Latest tool outputs
- Active constraints
- Temporary decisions

### 3. Session state

Structured facts the agent should keep available even after trimming raw history.

- Current goal
- Active plan
- Open issues
- Session-scoped preferences or overrides

### 4. Long-term memory

Durable user or project knowledge that survives across sessions.

- User preferences
- Domain facts
- Reusable project notes
- Prior decisions that should affect future runs

### 5. Retrieval corpus

External data indexed for on-demand retrieval.

- Documents
- Memory notes
- Artifacts
- Logs
- Prior summaries

## Core Best Practices

### 1. Slice conversation by complete turns, not raw message count

OpenAI's session-memory guidance defines a turn as one user message plus everything until the next user message, including assistant replies, reasoning, tool calls, and tool results. This is a better slicing unit than raw messages because it preserves execution boundaries and avoids cutting away tool context mid-task.

Practical implication:

- Trim by complete turns.
- Keep assistant and tool outputs attached to the initiating user turn.
- Do not drop intermediate tool results independently if the turn is still active.

### 2. Use a hybrid memory policy: tail + summary + state

Neither pure sliding windows nor pure summarization is sufficient.

- Sliding windows are deterministic, cheap, and good for short operational workflows, but they forget distant constraints abruptly.
- Summaries preserve long-range continuity, but they can introduce drift, omission, and context poisoning.

Recommended baseline:

- Preserve the last `N` complete turns verbatim.
- Compress older history into a structured summary or compaction artifact.
- Persist key facts separately as structured state so they do not depend on repeated summarization.

### 3. Choose `N` empirically, not by intuition

OpenAI's guidance recommends selecting `max_turns` based on real conversation distributions and average turns per issue. The right `N` depends on whether the workflow is transactional, investigative, or multi-issue.

Practical process:

1. Sample production conversations.
2. Measure turns per task or issue.
3. Evaluate how often key facts fall outside the retained tail.
4. Tune `N` against cost, latency, and task success, not token budget alone.

### 4. Separate raw transcript from structured state

The transcript is useful for immediate reasoning; it is a poor storage format for durable facts.

Keep a compact state object for:

- Current goal
- Acceptance criteria
- Open actions
- Known constraints
- User-scoped or session-scoped preferences

This reduces dependence on long transcripts and lowers the risk that important facts disappear during trimming or summarization.

### 5. Treat session notes as a staging layer

OpenAI's personalization guidance suggests a clear scope split:

- Latest user input
- Session overrides
- Global defaults

Session notes should be temporary by default. Promote them to long-term memory only when they prove durable.

Rule of thumb:

- "This trip has a budget under $2,000" is session-scoped.
- "The user prefers vegetarian meals" is a candidate for durable memory.

### 6. Prefer just-in-time retrieval over eager memory injection

Do not preload all memory into every prompt. Instead:

- Keep only the active tail and state in the hot path.
- Retrieve older notes, prior artifacts, or knowledge only when the current step needs them.

This improves focus, reduces token waste, and limits stale information from dominating current reasoning.

### 7. Keep tool outputs out of hot context once they are stale

Large tool results often dominate session bloat. Anthropic now exposes context editing specifically to clear old tool results; OpenAI's recent context guidance similarly favors compaction over preserving every historical payload verbatim.

Recommended pattern:

- Store raw tool outputs externally.
- Keep short summaries plus artifact references in context.
- Clear or compact stale tool payloads once the result has been absorbed into state, evidence, or a summary.

### 8. Use retrieval slices that match the memory type

"Slice" should not mean one universal chunking rule. Use different units for different retrieval targets:

| Memory type | Recommended slice | Why |
| --- | --- | --- |
| Recent dialogue | Complete turn | Preserves intent, tool calls, and result boundaries |
| Multi-issue dialogue | Issue summary or mini-summary | Enables pause/resume and handoff |
| Session state | Structured records | Highest precision for constraints and preferences |
| Durable memory | Atomic facts or notes with metadata | Easier dedupe, promotion, and deletion |
| Knowledge documents | Semantic chunks with overlap | Better recall during search |

### 9. Summaries should be structured and auditable

Free-form summaries drift over time. Prefer summaries with fixed fields such as:

- Current objective
- Decisions made
- Constraints
- Steps tried
- Tool outputs worth preserving
- Open questions
- Risks or known uncertainties

Also log:

- The summary prompt or compaction configuration
- The source range that was summarized
- The produced output

Without this, summary regressions are difficult to debug.

### 10. Evaluate memory systems on retrieval quality, not just token count

A memory system is only useful if it retrieves the right facts at the right time.

Track:

- Recall of key constraints
- Wrong-memory retrieval rate
- Summary drift rate
- Cost per successful task
- Latency added by summarization or retrieval
- Recovery quality after long sessions or handoffs

## Dedicated Focus: Session Memory Retrieval and Slicing

This section narrows the discussion to the part that most often breaks in production: how to retrieve useful session memory and how to slice conversation history so retrieval stays accurate.

### Retrieval goal

Session-memory retrieval is not the same as generic document RAG.

The job is not "find semantically similar text." The job is:

- recover the right constraint from the current session
- recover the right decision from the active issue
- recover the right tool result or failed attempt when it matters now
- avoid retrieving stale or irrelevant turns from an older branch of the conversation

That means session-memory retrieval should usually be:

- scope-aware
- time-aware
- issue-aware
- role-aware

and only secondarily semantic.

### Recommended retrieval order

Use the cheapest and most precise sources first:

1. `session_state`
   - Current goal, accepted constraints, open actions, active entities.
   - This should be read directly, not semantically searched.

2. `issue summaries`
   - Small summaries for the active topic or subtask.
   - Best source when a thread has multiple branches.

3. `turn summaries`
   - Short summaries of older complete turns.
   - Good for continuity when the raw tail was trimmed.

4. `raw complete turns`
   - Retrieve only when exact wording, exact tool parameters, or exact errors matter.

5. `artifacts`
   - Large tool outputs, reports, logs, or generated files.
   - Pull by reference, not by replaying everything into prompt.

This ordering prevents a common failure mode where a vector search returns a semantically similar but operationally irrelevant old utterance.

### Recommended slice types

Do not use one universal slice shape for session memory. Use slices that match the retrieval need.

| Slice type | What it contains | Best use | Retrieval key |
| --- | --- | --- | --- |
| Complete turn | One user message plus all assistant/tool activity until next user turn | Recovering local execution context | turn id, recency, semantic match |
| Issue slice | Summary of one topic, task, or branch | Multi-issue conversations, handoff, resume | issue id, status, recency |
| Step slice | One planning or execution step, result, and next action | Planner/operator workflows | step id, task id |
| Decision slice | Constraint, commitment, or resolved choice | Constraint recall and consistency | decision tag, entity, recency |
| Fact slice | Atomic session-scoped fact | Lightweight memory retrieval | entity, key, source |
| Artifact slice | URI plus short summary of a large output | Tool-heavy workflows | artifact id, tool name, source turn |

### Recommended slicing rules

#### 1. Slice raw dialogue by complete turn

For transcript retrieval, the complete turn is the default safe unit. It preserves:

- the triggering user request
- the assistant reasoning context
- the tool calls
- the tool outputs
- the final answer or failure state

Single-message retrieval is usually too brittle because it separates the user's ask from the execution that followed.

#### 2. Slice multi-issue conversations by issue, not by token window

If a session handles several tasks, create issue slices such as:

- objective
- decisions
- evidence used
- open questions
- current status

This makes pause/resume and branch switching much more reliable than replaying old turns and hoping semantic search finds the right branch.

#### 3. Slice large tool outputs into artifact summaries plus external references

Tool outputs should almost never stay in hot memory as raw payloads once the system has absorbed them.

Preferred pattern:

- store raw output externally
- generate a short artifact slice
- include source turn id, tool name, timestamp, and URI

Retrieve the artifact slice first, and only hydrate the raw artifact if the current step needs detail.

#### 4. Slice stable facts out of dialogue as structured records

If a fact is short, durable within the session, and likely to be reused, do not leave it trapped in transcript text.

Examples:

- active repository
- selected environment
- accepted budget
- currently blocked dependency
- preferred output format for this session

These should be promoted into structured session state or fact slices with metadata.

### Recommended retrieval pipeline

```text
Current user turn
  +
current task / step
  +
session_state
  |
  v
Query construction
  - active entities
  - issue id or branch id
  - constraint keywords
  - optional semantic query
  |
  v
Candidate generation
  - direct state lookup
  - issue slice lookup
  - turn-summary lookup
  - raw-turn fallback
  - artifact lookup
  |
  v
Reranking
  - same issue > same session > older branches
  - recent > stale
  - decisions / constraints > chit-chat
  - exact entity match > semantic similarity only
  |
  v
Prompt packing
  - session state
  - top issue slice
  - at most a few raw turns
  - artifact references
```

### Ranking signals that matter most

For session memory, the strongest ranking signals are usually:

1. Exact session scope
   - Never mix memories from another user or another business session.

2. Active issue or branch match
   - An older but same-issue slice is often more useful than a recent but different-topic slice.

3. Recency
   - Recent turns should generally win if all else is equal.

4. Decision and constraint salience
   - Constraints, commitments, selected options, and failures should be ranked above conversational filler.

5. Entity match
   - Repository name, customer id, ticket id, environment, document name.

6. Tool provenance
   - A retrieved result should preserve which tool produced it and in which turn.

Semantic similarity should be a secondary reranking feature, not the only signal.

### Prompt packing policy after retrieval

After retrieval, do not dump everything into the prompt.

Pack in this order:

1. structured session state
2. one active issue slice
3. one or two supporting turn summaries
4. raw turn excerpts only if exact wording or exact parameters matter
5. artifact references for heavy outputs

This keeps the prompt small and reduces cross-branch interference.

### Anti-patterns

#### 1. Applying document chunking defaults directly to chat history

OpenAI's `800 / 400` chunk defaults are sensible for file retrieval. They are usually not the right first choice for chat-history retrieval.

For session memory, token-based chunking can:

- split a tool call from its result
- split a user request from the assistant action
- mix unrelated branches into one chunk

#### 2. Retrieving isolated assistant messages

An assistant message without the user ask and tool context is often misleading. Prefer complete turns or issue summaries.

#### 3. Treating every memory as vector text

State, constraints, and decisions should often be direct keyed lookups rather than embedding search.

#### 4. Replaying stale tool payloads into every turn

Once a tool result has been summarized and externalized, raw payloads should usually stay out of hot context.

### Articles most relevant to session retrieval and slicing

#### OpenAI

- Session memory cookbook
  - https://developers.openai.com/cookbook/examples/agents_sdk/session_memory
  - Best source for complete-turn trimming, summarization trade-offs, and choosing `max_turns`.

- Context personalization and long-term memory notes
  - https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization
  - Best source for separating session-scoped notes from durable memory and for state-first memory design.

- Conversation state
  - https://developers.openai.com/api/docs/guides/conversation-state/
  - Best source for `conversation` objects, `previous_response_id`, and continuity mechanics.

- Compaction
  - https://developers.openai.com/api/docs/guides/compaction/
  - Best source for long-thread compaction behavior and what can be safely pruned.

- Retrieval guide
  - https://developers.openai.com/api/docs/guides/retrieval/
  - Best source for official chunking constraints and vector-store tuning.

- File search
  - https://developers.openai.com/api/docs/assistants/tools/file-search/
  - Best source for hosted retrieval defaults, query rewrite, hybrid search, and rerank.

#### Anthropic

- Effective context engineering for AI agents
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - Best source for the framing that context selection is the main engineering problem.

- Compaction
  - https://platform.claude.com/docs/en/build-with-claude/compaction
  - Best source for Anthropic's default recommendation for long-running conversations.

- Context editing
  - https://platform.claude.com/docs/en/build-with-claude/context-editing
  - Best source for clearing stale tool results and other targeted context cleanup.

- Memory tool
  - https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
  - Best source for just-in-time cross-session memory retrieval.

- Contextual Retrieval
  - https://www.anthropic.com/engineering/contextual-retrieval
  - Best source for improving retrieval quality when chunking removes too much local meaning.

## Retrieval and Chunking Guidance

### OpenAI defaults

OpenAI's hosted retrieval defaults are a reasonable baseline:

- Chunk size: `800` tokens
- Chunk overlap: `400` tokens
- Max chunks added to context: `20`

The hosted `file_search` tool also applies several retrieval optimizations out of the box:

- Query rewriting
- Breaking complex queries into multiple searches
- Hybrid keyword + semantic search
- Reranking

This is a strong default when the retrieval target is document-like knowledge rather than short session facts.

### When to change chunking

OpenAI's retrieval docs allow `100` to `4096` tokens per chunk, with overlap not exceeding half the chunk size.

Practical guidance:

- Use smaller slices for dense procedural docs or code-like material.
- Use larger slices for narrative or policy text where local context spans paragraphs.
- Retain overlap to avoid splitting a decisive detail across boundaries.
- Add metadata aggressively so retrieval can filter by user, session, source, topic, or recency.

### Session memory is not standard RAG

Session-memory retrieval should usually prefer:

- turn IDs
- issue IDs
- timestamps
- role boundaries
- user/session scope
- recency weighting

This is different from generic document RAG, where semantic chunk similarity dominates. Memory retrieval benefits more from precise scope and lifecycle metadata than from raw vector similarity alone.

## OpenAI: Recommended Patterns

### 1. Use Responses API conversation state for continuity

OpenAI recommends either:

- a durable `conversation` object, or
- `previous_response_id` chains

This handles basic conversation continuity, but not automatic memory management.

### 2. Use explicit compaction for long-running threads

OpenAI now provides server-side compaction for the Responses API through `context_management` with `compact_threshold`.

Key points:

- Compaction is triggered when the rendered token count crosses the configured threshold.
- The returned compaction item is opaque and carries forward key prior state and reasoning.
- With stateless chaining, older items before the newest compaction item can be dropped to reduce latency.
- With `previous_response_id`, OpenAI explicitly advises not to manually prune.

### 3. Keep short-term memory explicit in the app layer

OpenAI's session-memory cookbook still presents application-managed memory patterns as first-class:

- trimming to last `N` turns
- summarizing older turns into a structured carry-forward summary

This suggests that even with built-in conversation state, developers should still control short-term memory policy deliberately.

### 4. Model long-term memory as state plus notes, not just vector recall

The personalization cookbook favors a stateful pattern:

- inject structured user profile and memory notes at session start
- save candidate memories during the session
- re-inject session notes when context is trimmed
- consolidate durable notes asynchronously at session end

This is closer to a state-management design than a pure semantic search design.

### 5. Let hosted retrieval handle generic document search

For knowledge-base retrieval, OpenAI's hosted `file_search` already bakes in query rewrite, hybrid search, rerank, and chunk defaults. This lowers the amount of custom retrieval logic needed for standard RAG paths.

## Anthropic: Recommended Patterns

### 1. Treat context engineering as the main problem

Anthropic's recent guidance reframes the task from prompt engineering to context engineering: the central question is which tokens should be present for the current inference.

Core implication:

- More context is not automatically better.
- Large windows still suffer from context rot.
- Retrieval quality depends on curation, not only capacity.

### 2. Prefer server-side compaction for long-running agent workflows

Anthropic's context-window and compaction docs state that server-side compaction is the primary or recommended strategy for long-running conversations and agentic workflows.

Practical implication:

- Start with compaction as the default long-thread policy.
- Reach for fine-grained editing only when specific payloads need special handling.

### 3. Use context editing to clear stale payloads

Anthropic's context editing is aimed at specialized scenarios:

- clear old tool results in tool-heavy workflows
- clear thinking blocks when using extended thinking

This is effectively an official recommendation to shrink hot context by removing categories of stale content instead of letting them accumulate indefinitely.

### 4. Use prompt caching for repeated prefixes and growing histories

Anthropic's prompt caching is especially relevant when a session has:

- stable instructions
- stable tools
- large static prefixes
- long but incrementally growing histories

This is a cost and latency optimization rather than a memory design by itself, but it strongly complements long-running sessions.

### 5. Use the memory tool for cross-session recall

Anthropic's memory tool is explicitly positioned as a primitive for just-in-time context retrieval:

- store knowledge outside the active context window
- retrieve it on demand in later conversations

This aligns with the layered memory model above and argues against eagerly loading durable memory into every session.

### 6. Improve RAG with contextual retrieval

Anthropic's Contextual Retrieval recommends contextual embeddings and contextual BM25 to restore local meaning that is otherwise lost during chunking.

A notable Anthropic recommendation:

- if the knowledge base is smaller than roughly `200k` tokens, first test including the whole corpus directly in prompt instead of introducing RAG complexity

This is especially relevant for tightly bounded domain assistants with a small but high-value corpus.

## Aether Frame Implications

### 1. Separate business session continuity from memory policy

Current Aether Frame documents already distinguish business `chat_session_id` from framework-specific session state. That separation should remain.

Recommended addition:

- `chat_session_id` controls continuity and recovery.
- memory policy controls what context is kept hot, compacted, externalized, or retrieved.

These are related but distinct concerns.

### 2. Add a first-class session memory model

Rather than treating session history as a single opaque transcript, split it into:

- `conversation_tail`
- `session_summary`
- `session_state`
- `session_artifacts`
- `durable_memory_candidates`

This makes trimming, recovery, and retrieval deterministic.

### 3. Prefer state-backed recovery over transcript-only recovery

The current recovery strategy stores transcripts for replay. That is useful, but it should evolve toward a richer recovery payload:

- last `N` turns
- latest structured session state
- latest summary or compaction-equivalent artifact
- references to large tool outputs or artifacts

This would reduce rehydration cost and improve resilience after long sessions.

### 4. Introduce explicit promotion rules

Candidate memories should move through a lifecycle:

1. observed during a session
2. stored as a session note
3. promoted to durable memory only if stable or repeated
4. deduplicated or superseded when newer facts arrive

This is safer than writing every extracted fact into a long-term memory store immediately.

### 5. Use different retrieval paths for memory and knowledge

Do not collapse all retrieval into one vector store abstraction.

Suggested split:

- Session-memory retrieval: turn summaries, state snapshots, issue notes, timeline-aware access
- Knowledge retrieval: document chunks, hybrid search, rerank
- Artifact retrieval: explicit URIs for logs, reports, tool outputs

## Recommended Baseline Architecture

```text
User Request
  |
  v
Conversation Continuity
  - chat_session_id
  - framework session handle
  |
  v
Hot Context Assembly
  - system / task
  - last N complete turns
  - current session state
  - selected tool scope
  |
  v
Overflow Handling
  - compact / summarize old turns
  - extract durable candidates
  - externalize raw tool outputs
  |
  v
On-Demand Retrieval
  - session notes
  - durable memory
  - knowledge chunks
  - artifacts
  |
  v
Model Call
  |
  v
Post-Run Lifecycle
  - update session state
  - update session summary
  - store artifacts
  - evaluate durable-memory promotion
```

## Recommended Adoption Order

1. Keep last `N` complete turns and define `N` from observed traffic.
2. Add a structured session summary with fixed fields.
3. Add explicit `session_state` separate from transcript text.
4. Store large tool outputs as artifacts and stop replaying them verbatim.
5. Add session-note promotion rules for durable memory.
6. Introduce memory retrieval and knowledge retrieval as separate pipelines.
7. Add evaluation for recall, drift, and wrong-memory retrieval.

## Source Links

### OpenAI

- Conversation state: https://developers.openai.com/api/docs/guides/conversation-state/
- Compaction: https://developers.openai.com/api/docs/guides/compaction/
- Retrieval guide: https://developers.openai.com/api/docs/guides/retrieval/
- File search: https://developers.openai.com/api/docs/assistants/tools/file-search/
- Session memory cookbook: https://developers.openai.com/cookbook/examples/agents_sdk/session_memory
- Personalization and long-term memory notes: https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization

### Anthropic

- Effective context engineering for AI agents: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Context windows: https://platform.claude.com/docs/en/build-with-claude/context-windows
- Compaction: https://platform.claude.com/docs/en/build-with-claude/compaction
- Context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
- Prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Memory tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- Contextual Retrieval: https://www.anthropic.com/engineering/contextual-retrieval
- Product note on context management: https://www.anthropic.com/news/context-management
