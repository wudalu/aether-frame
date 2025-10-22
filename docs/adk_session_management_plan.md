## Short- and Long-Term Goals

### Short-Term (next 1–2 sprints)
- Stabilize lazy ADK session initialization so agent creation never allocates ADK sessions until the first conversation request arrives.
- Provide comprehensive tests that cover the creation → first message flow (unit + integration) to prevent regressions.
- Document public expectations for `session_id` handling so downstream services know when to pass business vs. ADK identifiers.

### Long-Term (next 1–2 quarters)
- Introduce persistent storage for cross-restart session recovery and lifecycle analytics.
- Expand the session manager to support cross-framework adapters (e.g., AutoGen, LangGraph) with a shared orchestration contract.
- Implement configurable cleanup policies (time-based, idle thresholds) and expose metrics for observability dashboards.

## Execution Plan

1. **Finalize Lazy Session Initialization (Week 1)**
   - Audit all entry points (adapter, runner manager, domain agent) to ensure sessions are materialized on-demand only.
   - Add regression tests covering business chat vs. ADK session ID translation.

2. **Enhance Documentation and Contract Clarity (Week 2)**
   - Update developer docs and API guides describing required fields and ID semantics.
   - Provide example flows for custom chat session usage across creation and conversation APIs.

3. **Broaden Test Coverage (Week 2–3)**
   - Build integration tests that run through agent creation, first user message, session switch, and teardown.
   - Include mock-backed tests for session history migration to catch regressions early.

4. **Plan for Persistence and Cross-Framework Support (Week 4+)**
   - Draft design notes for persisting session metadata and history in external storage.
   - Define abstraction boundaries so additional frameworks can reuse session coordination logic without duplicating code.
