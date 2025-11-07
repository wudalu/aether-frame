# Unit Test Coverage Expansion Plan

## Goals and Constraints
- Raise overall unit test coverage for `src/aether_frame` while preserving existing integration and E2E suites.
- Follow the architectural stack in `docs/architecture.md`: progress from the application execution layer down to infrastructure and utilities.
- Cap each implementation wave at approximately 2,000 new lines of test code to simplify reviews and reduce regression risk.
- Maintain pytest best practices: async-aware fixtures, clear Arrange/Act/Assert structure, and deterministic assertions (no sleeps, avoid brittle ordering).
- Keep documentation, fixtures, and helper utilities in English, aligning with repository policy.

## Baseline and Measurement
- Establish a repeatable baseline by running `python -m pytest --cov src/aether_frame --cov-report=term-missing --cov-report=xml`.
- Store generated `coverage.xml` under `reports/coverage/<timestamp>/` (add gitignore entry if required) and track deltas per wave.
- Record module-level coverage deltas in this document after each wave; flag areas that regress below previously recorded values.
- Adopt 5% incremental coverage checkpoints: target ≥65% after wave 1, ≥72% after wave 2, ≥78% after wave 3, then ≥83% after wave 4; revisit targets once tooling-heavy modules land.

## Iteration Workflow
1. **Select module scope** – choose a cohesive slice from the next architectural layer without exceeding the 2,000 LOC ceiling.
2. **Gap analysis** – inspect implementation files and existing tests (`tests/unit`, `tests/integration`, manual suites) to catalog missing behaviors or error paths.
3. **Test design** – outline fixtures, mocks, and parametrizations; prefer lightweight stubs over full ADK integrations.
4. **Implementation** – add tests, shared fixtures, and minimal helper utilities; keep helpers reusable across subsequent waves.
5. **Validation** – run focused pytest selections plus `python -m pytest --cov ...` to confirm coverage delta; record results and update this plan.
6. **Debrief** – capture lessons learned, helper reuse opportunities, and open risks before advancing to the next wave.

## Prioritized Module Backlog
### Wave 1 – Application Execution Layer
| Component | Current Coverage Notes | Planned Test Focus | Est. Added LOC |
|-----------|------------------------|--------------------|----------------|
| `execution/ai_assistant.py` | Minimal direct unit tests; behavior only exercised indirectly via E2E suites. | Validation error paths, engine failure propagation, live session bootstrap, health check metadata. | 250–300 |
| `execution/execution_engine.py` | Covered mainly through integration suites; lacks isolated tests for routing modes and error shaping. | Three execution modes (agent/session/config), retry & timeout handling, exception wrapping, shutdown lifecycle. | 450–550 |
| `execution/task_router.py` | No dedicated unit coverage. | Strategy selection heuristics, fallback routing, logging metadata, planner presence/absence. | 200–250 |
| `execution/task_factory.py` | Large surface area without targeted tests. | Task creation from configs, parameter validation, ADK-specific overrides, error reporting on malformed input. | 450–500 |
| `execution/ai_assistant.start_live_session` path | Only smoke-tested manually. | Ensure execution context defaults, error conversion when execution engine raises, cooperative cancellation behavior. | Included above |

### Wave 2 – Framework Abstraction Layer
| Component | Current Coverage Notes | Planned Test Focus | Est. Added LOC |
|-----------|------------------------|--------------------|----------------|
| `framework/framework_registry.py` | Basic scenarios exercised indirectly; no registry lifecycle tests. | Adapter registration/unregistration, singleton reuse, error behavior when adapter missing. | 150–200 |
| `framework/adk/runner_manager.py` | Partially covered through session manager tests; gaps around cleanup, warm pool, and metrics. | Idle cleanup decisions, multi-runner balancing, failure handling for runner provisioning, monitoring hooks. | 400–450 |
| `framework/adk/adk_session_manager.py` | Heavy existing coverage but missing chat history migration paths (failing e2e tests). | Fix existing failing suites, add focused unit cases for history extraction/injection and recovery callbacks. | 250–300 |
| `framework/adk/approval_broker.py` | No tests. | Approval escalation paths, timeout fallbacks, audit log emission. | 200–250 |
| `framework/adk/model_factory.py`, `deepseek_llm.py`, `deepseek_streaming_llm.py` | Only manual tests. | Model selection based on config, streaming callback wiring, error mapping for provider failures. | 400–450 |
| `framework/adk/multimodal_utils.py` | Untested. | Media payload normalization, ADK format conversion, validation errors. | 150–200 |

### Wave 3 – Core Agent Layer
| Component | Current Coverage Notes | Planned Test Focus | Est. Added LOC |
|-----------|------------------------|--------------------|----------------|
| `agents/manager.py` | No unit tests. | Agent registration lifecycle, duplicate handling, cleanup hooks, stats reporting. | 250–300 |
| `agents/adk/adk_domain_agent.py` | Partially covered; lacks tests for tool proposal synthesis, planner metadata, exception translation. | Expand to include persistent state handling, streaming events, multi-turn session reuse, tool error propagation. | 500–600 |
| `agents/adk/tool_conversion.py` | No coverage. | Conversion fidelity between internal tool specs and ADK forms, validation of optional fields. | 150–200 |
| `agents/adk/adk_agent_hooks.py` | Untested. | Hook sequencing, telemetry emission, failure isolation. | 150–200 |
| `agents/adk/adk_event_converter.py` | Existing coverage; extend for edge ADK events lacking type markers. | Additional parametrized cases for fallback heuristics and error logging. | 100–150 |

### Wave 4 – Tool Service Layer
| Component | Current Coverage Notes | Planned Test Focus | Est. Added LOC |
|-----------|------------------------|--------------------|----------------|
| `tools/service.py` & `tools/resolver.py` | Basic streaming tests only. | Tool lookup precedence, caching, execution fallback, timeout handling, telemetry emission. | 350–400 |
| `tools/builtin/tools.py` & `chat_log_tool.py` | Limited smoke coverage. | Input validation, contextual metadata, chat log serialization edge cases. | 200–250 |
| `tools/mcp/*` | No automated tests. | Client handshake, config validation, wrapper error handling, reconnection strategies. | 450–500 |
| `tools/base/tool.py` | Untested. | Abstract contract enforcement, subclass validation, default behaviors. | 100–150 |

### Wave 5 – Common, Contracts, and Streaming
| Component | Current Coverage Notes | Planned Test Focus | Est. Added LOC |
|-----------|------------------------|--------------------|----------------|
| `common/utils.py`, `common/interaction_logger.py`, `common/unified_logging.py` | No systematic coverage. | Time formatting helpers, structured logging payloads, error branches. | 250–300 |
| `contracts/*` | Partially exercised via integration. | Serialization/deserialization, validation constraints, backward compatibility for enums and request models. | 250–300 |
| `streaming/stream_session.py` | Minimal targeted tests. | State transitions, chunk buffering, cancellation and timeout behavior. | 250–300 |

### Wave 6 – Infrastructure and Bootstrap
| Component | Current Coverage Notes | Planned Test Focus | Est. Added LOC |
|-----------|------------------------|--------------------|----------------|
| `infrastructure/session/*`, `infrastructure/storage/*` | Sparse or absent coverage. | Persistence adapters, reconnection logic, error bubbling when storage backends fail. | 350–400 |
| `infrastructure/logging/*` & monitoring | No unit tests. | Ensure log enrichment, metric exports, and guard rails against recursive logging. | 200–250 |
| `bootstrap` + configuration | Verified only via large E2E flows. | Phase-by-phase initialization, failure rollback, configuration overrides. | 250–300 |

_Later waves can extend to framework placeholders (AutoGen, LangGraph) once ADK-focused coverage stabilizes._

## Shared Test Infrastructure Improvements
- Build a `tests/fixtures/factories.py` module with reusable builders for `TaskRequest`, `ExecutionContext`, ADK runner/session mocks, and tool descriptors.
- Introduce async-friendly helper mixins (e.g., `AsyncMockRunner`) to avoid re-implementing mock runner managers across tests.
- Add parametrized data sets for multimodal payloads to reduce duplication when exercising media conversions.
- Leverage `pytest.mark.parametrize` for configuration matrix coverage, and `pytest.mark.asyncio` / `pytest.mark.timeout` to keep async tests deterministic.
- Use `freezegun` or `datetime` monkeypatching for time-dependent code; avoid relying on real `datetime.now()` in assertions.

## Quality Gates and Reporting
- Enforce `pytest --maxfail=1` inside CI runs for new waves to keep failure signals crisp.
- Add coverage thresholds to `pyproject.toml` (e.g., `[tool.pytest.ini_options] addopts = "--cov=src/aether_frame --cov-report=term-missing --cov-fail-under=65"` and update per wave).
- Integrate coverage trend tracking into `docs/code_ut.md` after each wave: append a short log entry with date, scope, and coverage delta.
- Keep manual debugging suites (`tests/manual`, `tests/debug`) untouched; as coverage improves, consider migrating any stable logic from manual suites into automated ones.

## Reference Checklist per Wave
1. Confirm targeted files and expected LOC additions.
2. Draft or extend fixtures/utilities required for the scope.
3. Implement and review tests, ensuring naming aligns with `test_<feature>.py`.
4. Run `python -m pytest` plus relevant `-k` selections; capture coverage artifacts.
5. Update this plan: document completed scope, measured coverage, newly added fixtures, and follow-up items.
6. Create follow-up tickets for any uncovered branches deferred due to the 2,000 LOC limit.

By following this staged plan we can iteratively raise unit coverage, unlock faster regressions, and keep changes reviewable even as we span the full architecture stack.

## Active Wave – May 2025 Coverage Push

| Step | Target Modules | Success Criteria | Planned Test Activities |
|------|----------------|------------------|-------------------------|
| 1 | `agents/adk/adk_domain_agent.py` | ≥65% module coverage with live/streaming error cases validated | Extend unit suites to cover `_run_adk_with_runner_and_agent`, `_execute_with_adk_runner` error branches, and `_create_error_live_result` streaming fallbacks using stub runners plus synthetic ADK events. |
| 2 | `framework/adk/adk_adapter.py`, `framework/adk/adk_session_manager.py` | Adapter ≥55%, Session Manager ≥65% | Build adapter-focused tests that simulate runner/session lifecycles (`_execute_task`, recovery replay, idle cleanup) and reuse fixtures in `tests/unit/test_adk_session_manager_core.py` to validate archive/injection/teardown paths. |
| 3 | `framework/adk/model_factory.py`, `framework/adk/multimodal_utils.py` | Model factory ≥40%, multimodal utils ≥75% | Introduce isolates for provider selection (happy path + fallback) and multimodal payload transforms (text/image/error), using Settings stubs to emulate environment toggles. |
| 4 | `tools/builtin/chat_log_tool.py`, `tools/mcp/tool_wrapper.py` | Each ≥80% | Add append-mode/validation/error coverage for the chat log tool and exercise MCP wrapper streaming, metadata propagation, and timeout handling. Only `tests/` modifications (plus this document) are permitted per user guidance. |

Each step follows the agreed cadence: (a) modify files under `tests/`, (b) run targeted `pytest -k <scope>` selections, (c) execute `python3 -m pytest tests/unit --cov src/aether_frame --cov-report=term`, (d) commit, then proceed to the next step. Document coverage deltas here after finishing every step.
