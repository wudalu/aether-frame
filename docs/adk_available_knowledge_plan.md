# ADK Knowledge Integration Roadmap

## MVP Goal
- Persist user-provided `available_knowledge` across ADK chat sessions.
- Surface the same knowledge to runtime components via metadata and memory entries.
- Provide a minimal retrieval path so agents can leverage the stored knowledge when needed.

## Near-Term Plan
1. **Attach a MemoryService to ADK runners**
   - Instantiate `InMemoryMemoryService` in `RunnerManager._create_new_runner`.
   - Store the service handle inside the runner context for later use.
2. **Convert and store knowledge**
   - Transform each `KnowledgeSource` into a lightweight `MemoryEntry`.
   - Call `memory_service.store_memory(app_name, user_id, entry)` once per source after session coordination.
   - Track synced sources in `ChatSessionInfo` metadata to avoid duplicate writes.
3. **Expose a basic retrieval tool**
   - Add a `knowledge_lookup` tool that invokes `tool_context.search_memory`.
   - Return the top snippets directly to the model for immediate grounding.
4. **Validate with focused tests**
   - Unit test to confirm memory storage is triggered.
   - Unit test for the retrieval tool returning snippets.

## Retrieval Flow (MVP Detail)
1. Memory service reference:
   - Store the instantiated `memory_service` inside each runner context (e.g., `runner_context["memory_service"] = memory_service`).
   - Ensure `runtime_context` created by `AdkFrameworkAdapter` carries this handle through to the domain agent.
2. Conversion helper:
   - Translate each `KnowledgeSource` into a `MemoryEntry` with fields such as `title=source.name`, `text` combining description/location, and `metadata=source.metadata`.
3. Write-once strategy:
   - After session coordination, call `store_memory(app_name, user_id, entry)` for any new knowledge source.
   - Track synced sources in `chat_session.metadata.setdefault("synced_knowledge", set())`.
4. Retrieval trigger options:
   - Manual lookup inside `AdkDomainAgent.execute_with_runtime`: call `memory_service.search_memory(app_name, user_id, query)` and prepend snippets to the prompt before invoking ADK.
   - Tool-based lookup: wrap the same call inside a simple `knowledge_lookup` tool and return the top N snippets to the model.
5. Prompt integration:
   - For manual lookup, append snippets as a system message or metadata prior to agent execution.
   - For the tool, return structured data (e.g., `{"snippets": [...]}`) so the LLM can read the content directly.

## Long-Term Enhancements
- Support pluggable memory backends (Vertex AI RAG, Vertex AI Search, custom implementations).
- Automate retrieval triggers via agent hooks and prioritize relevant snippets.
- Enrich `MemoryEntry` metadata (embeddings, tags, freshness) for smarter filtering.
- Add observability: log ingestion success/failure, retrieval effectiveness, and stale knowledge cleanup.

## Implementation Checklist
- [x] Instantiate and store `memory_service` during runner creation.
- [x] Expose `memory_service` via runtime context and conversion helper.
- [x] Write knowledge entries post-session coordination with dedupe guard.
- [x] Add manual retrieval inside `AdkDomainAgent.execute_with_runtime` (plus optional tool).
- [x] Update tests to cover knowledge storage, retrieval snippets, and duplication checks.

## Current Integration Touchpoints
- `RunnerManager._create_new_runner` (`src/aether_frame/framework/adk/runner_manager.py`): instantiates `InMemoryMemoryService` when available and stores it in the runner context.
- `AdkSessionManager.coordinate_chat_session` (`src/aether_frame/framework/adk/adk_session_manager.py`): syncs `available_knowledge` into runner memory via `_sync_knowledge_to_memory`, deduplicating with `ChatSessionInfo.synced_knowledge_sources`.
- `AdkDomainAgent._execute_with_adk_runner` (`src/aether_frame/agents/adk/adk_domain_agent.py`): retrieves snippets before execution using `_retrieve_memory_snippets` and appends them to outbound messages.
- Tests (`tests/unit/test_adk_session_manager_idle.py`, `tests/unit/test_adk_domain_agent_memory.py`, `tests/integration/test_adk_knowledge_integration.py`): cover storage, dedupe, retrieval, and end-to-end flow.
