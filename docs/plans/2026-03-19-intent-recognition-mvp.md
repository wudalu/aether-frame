# Intent Recognition MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a pluggable intent-recognition MVP that runs inside the existing ADK execution path before the first main-task LLM call, can short-circuit into one clarification turn containing 1 to 3 targeted questions, and passes a structured intent artifact downstream without changing the external request/response flow.

**Architecture:** Keep `TaskRequest -> ExecutionEngine -> AdkFrameworkAdapter -> AgentRequest -> AdkDomainAgent -> ADK Runtime` unchanged. Add a separate `src/aether_frame/intent/` package for contracts, pipelines, state store, and integration helpers; wire the selected pipeline through `bootstrap.py` and `adk_adapter.py`; then add one narrow pre-LLM seam in `adk_domain_agent.py` to invoke the intent stage before `_execute_with_adk_runner(...)`.

**Tech Stack:** Python, existing dataclass contracts, existing ADK adapter/runtime wiring, pytest via `uv run pytest`

Cross references:
- `docs/intent-recognition_design.md`
- `docs/research/2026-03-18-agent-intent-recognition.md`
- `src/aether_frame/framework/adk/adk_adapter.py`
- `src/aether_frame/agents/adk/adk_domain_agent.py`

## Scope Guardrails

Keep the MVP narrow:

1. no extra outer orchestration layer
2. no embeddings or vector retrieval
3. no external intent catalog loader
4. no Redis-backed clarification state
5. no multi-agent split
6. no global shared model-invoker refactor
7. no broad contract churn in `TaskRequest` / `TaskResult`

For the MVP, the intent artifact should be attached to metadata and made available to downstream context code, but the plan should not try to redesign the entire context layer in the same change.

## Phase Breakdown

### Phase 1: Foundation

Outcome:

1. a standalone `intent/` package exists
2. settings can enable/disable the feature
3. the artifact and pipeline contracts are stable

### Task 1: Add settings and intent contracts

**Files:**
- Create: `src/aether_frame/intent/__init__.py`
- Create: `src/aether_frame/intent/contracts.py`
- Create: `src/aether_frame/intent/pipeline.py`
- Create: `src/aether_frame/intent/registry.py`
- Modify: `src/aether_frame/config/settings.py`
- Test: `tests/unit/test_intent_contracts.py`
- Test: `tests/unit/test_config_modules.py`

**Step 1: Write the failing tests**

Add tests for:

1. `Settings` exposes:
   - `enable_intent_recognition`
   - `intent_pipeline_type`
   - `intent_max_clarification_turns`
   - `intent_max_clarification_questions`
   - `intent_enable_llm_judgment`
2. `IntentRecognitionResult` defaults are stable
3. the MVP intent registry exposes a small static set of `IntentSpec` and `SlotSpec`
4. `PendingIntentState` keeps `session_id`, `prior_intent`, and `clarification_turns`

Example test skeleton:

```python
def test_settings_expose_intent_defaults():
    settings = Settings()
    assert settings.enable_intent_recognition is False
    assert settings.intent_pipeline_type == "noop"


def test_intent_recognition_result_defaults():
    result = IntentRecognitionResult(intent="unknown")
    assert result.slots == {}
    assert result.missing_slots == []
    assert result.needs_clarification is False
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_intent_contracts.py tests/unit/test_config_modules.py -v
```

Expected:

1. failure because the new settings and intent contracts do not exist yet

**Step 3: Write the minimal implementation**

Add:

```python
@dataclass
class IntentRecognitionResult:
    intent: str
    confidence: Optional[float] = None
    slots: Dict[str, Any] = field(default_factory=dict)
    missing_slots: List[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_questions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

and:

```python
class IntentRecognitionPipeline(Protocol):
    async def recognize(
        self,
        agent_request: AgentRequest,
        runtime_context: Dict[str, Any],
    ) -> IntentRecognitionResult:
        ...
```

Recommended settings defaults:

1. `enable_intent_recognition: bool = False`
2. `intent_pipeline_type: str = "noop"`
3. `intent_max_clarification_turns: int = 1`
4. `intent_max_clarification_questions: int = 3`
5. `intent_enable_llm_judgment: bool = True`

Recommended registry rule:

1. keep the initial `IntentSpec` registry in `src/aether_frame/intent/registry.py`
2. define 3 to 5 supported intents maximum
3. each required slot should include its own clarification question

**Step 4: Run the tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_intent_contracts.py tests/unit/test_config_modules.py -v
```

Expected:

1. all targeted tests pass

**Step 5: Commit**

```bash
git add src/aether_frame/intent/__init__.py src/aether_frame/intent/contracts.py src/aether_frame/intent/pipeline.py src/aether_frame/intent/registry.py src/aether_frame/config/settings.py tests/unit/test_intent_contracts.py tests/unit/test_config_modules.py
git commit -m "feat: add intent recognition contracts and settings"
```

### Phase 2: Standalone Intent Module

Outcome:

1. `NoOpIntentPipeline` and `HybridIntentPipeline` exist
2. there is an in-memory clarification state store
3. the module can be tested without touching ADK runtime code

### Task 2: Add no-op pipeline and in-memory state store

**Files:**
- Create: `src/aether_frame/intent/default_pipeline.py`
- Create: `src/aether_frame/intent/state_store.py`
- Test: `tests/unit/test_intent_pipeline_noop.py`
- Test: `tests/unit/test_intent_state_store.py`

**Step 1: Write the failing tests**

Add tests for:

1. `NoOpIntentPipeline` returns a pass-through result
2. `InMemoryIntentStateStore` can save, load, and clear one pending clarification
3. state store uses `session_id` as the lookup key

Example test skeleton:

```python
@pytest.mark.asyncio
async def test_noop_pipeline_returns_unknown_without_clarification():
    pipeline = NoOpIntentPipeline()
    result = await pipeline.recognize(agent_request, runtime_context={})
    assert result.intent == "unknown"
    assert result.needs_clarification is False
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_intent_pipeline_noop.py tests/unit/test_intent_state_store.py -v
```

Expected:

1. failure because the pipeline and store do not exist yet

**Step 3: Write the minimal implementation**

Implementation rules:

1. `NoOpIntentPipeline` must never trigger an LLM call
2. state store stays local to `src/aether_frame/intent/`
3. keep expiration simple; do not add Redis in MVP

Recommended store surface:

```python
class InMemoryIntentStateStore:
    async def save(self, state: PendingIntentState) -> None: ...
    async def load(self, session_id: str) -> Optional[PendingIntentState]: ...
    async def clear(self, session_id: str) -> None: ...
```

**Step 4: Run the tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_intent_pipeline_noop.py tests/unit/test_intent_state_store.py -v
```

Expected:

1. all targeted tests pass

**Step 5: Commit**

```bash
git add src/aether_frame/intent/default_pipeline.py src/aether_frame/intent/state_store.py tests/unit/test_intent_pipeline_noop.py tests/unit/test_intent_state_store.py
git commit -m "feat: add noop intent pipeline and in-memory state store"
```

### Task 3: Implement the hybrid MVP pipeline

**Files:**
- Modify: `src/aether_frame/intent/default_pipeline.py`
- Modify: `src/aether_frame/intent/registry.py`
- Test: `tests/unit/test_intent_pipeline.py`

**Step 1: Write the failing tests**

Add tests for:

1. deterministic fast path recognizes obvious supported intents
2. ambiguous requests trigger `needs_clarification=True`
3. unsupported requests return `intent="unknown"`
4. optional LLM judgment is only called when deterministic narrowing is insufficient

Example test skeleton:

```python
@pytest.mark.asyncio
async def test_hybrid_pipeline_uses_fast_path_before_llm():
    llm_calls = 0

    async def fake_llm(*args, **kwargs):
        nonlocal llm_calls
        llm_calls += 1
        return {"intent": "unknown"}

    pipeline = HybridIntentPipeline(llm_classifier=fake_llm)
    result = await pipeline.recognize(agent_request, runtime_context={})

    assert result.intent == "analyze_requirement"
    assert llm_calls == 0
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_intent_pipeline.py -v
```

Expected:

1. failure because `HybridIntentPipeline` behavior is not implemented

**Step 3: Write the minimal implementation**

Implementation rules:

1. keep the initial intent set hard-coded and small
2. start with deterministic narrowing from `TaskRequest.description` and latest user message
3. call the optional LLM classifier only after the cheap fast path cannot decide
4. do not build a shared global model invoker in MVP
5. if LLM judgment is unavailable or fails, degrade gracefully to clarification or `unknown`

Recommended supported MVP intents:

1. `analyze_requirement`
2. `generate_draft`
3. `explain_capability`
4. `unknown`

Clarification selection rule:

1. pick up to `intent_max_clarification_questions`
2. only ask for required missing slots
3. order by `clarification_priority`

**Step 4: Run the tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_intent_pipeline.py -v
```

Expected:

1. all targeted tests pass

**Step 5: Commit**

```bash
git add src/aether_frame/intent/default_pipeline.py tests/unit/test_intent_pipeline.py
git commit -m "feat: add hybrid intent pipeline"
```

### Phase 3: Runtime Wiring

Outcome:

1. bootstrap can configure the selected pipeline
2. ADK adapter passes pipeline dependencies into runtime context
3. no outer flow changes are introduced

### Task 4: Wire the configured pipeline through bootstrap and adapter

**Files:**
- Create: `src/aether_frame/intent/integration.py`
- Modify: `src/aether_frame/bootstrap.py`
- Modify: `src/aether_frame/framework/adk/adk_adapter.py`
- Test: `tests/unit/test_bootstrap_flow.py`
- Test: `tests/unit/test_intent_integration.py`

**Step 1: Write the failing tests**

Add tests for:

1. bootstrap creates the configured pipeline implementation
2. bootstrap passes the pipeline into the ADK adapter without changing other startup behavior
3. adapter includes `intent_pipeline` and `intent_state_store` in the runtime context it gives to the domain agent

Example test skeleton:

```python
@pytest.mark.asyncio
async def test_bootstrap_wires_hybrid_intent_pipeline(monkeypatch):
    settings = Settings(
        enable_intent_recognition=True,
        intent_pipeline_type="hybrid",
    )
    components = await bootstrap.initialize_system(settings)
    assert hasattr(components.framework_registry.adapter, "set_intent_pipeline")
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_bootstrap_flow.py tests/unit/test_intent_integration.py -v
```

Expected:

1. failure because pipeline wiring does not exist yet

**Step 3: Write the minimal implementation**

Implementation rules:

1. follow the existing `set_skill_catalog(...)` pattern in `AdkFrameworkAdapter`
2. keep wiring logic in `bootstrap.py`
3. keep `TaskRequest -> ExecutionEngine -> AdkFrameworkAdapter -> AgentRequest -> AdkDomainAgent -> ADK Runtime` unchanged

Recommended adapter seam:

```python
def set_intent_pipeline(self, intent_pipeline, intent_state_store=None) -> None:
    self._intent_pipeline = intent_pipeline
    self._intent_state_store = intent_state_store
```

and in `_execute_with_domain_agent(...)`:

```python
domain_agent.runtime_context.update(
    {
        "intent_pipeline": self._intent_pipeline,
        "intent_state_store": self._intent_state_store,
    }
)
```

**Step 4: Run the tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_bootstrap_flow.py tests/unit/test_intent_integration.py -v
```

Expected:

1. all targeted tests pass

**Step 5: Commit**

```bash
git add src/aether_frame/intent/integration.py src/aether_frame/bootstrap.py src/aether_frame/framework/adk/adk_adapter.py tests/unit/test_bootstrap_flow.py tests/unit/test_intent_integration.py
git commit -m "feat: wire intent pipeline through bootstrap and adapter"
```

### Phase 4: Agent Pre-LLM Seam

Outcome:

1. the agent runs intent recognition before the main ADK model request
2. clarification can short-circuit with `TaskStatus.PARTIAL`
3. recognized artifacts are available downstream through metadata

### Task 5: Add the pre-LLM intent stage in `AdkDomainAgent.execute()`

**Files:**
- Modify: `src/aether_frame/agents/adk/adk_domain_agent.py`
- Modify: `src/aether_frame/intent/integration.py`
- Modify: `src/aether_frame/intent/default_pipeline.py`
- Test: `tests/unit/test_adk_domain_agent_execution_paths.py`
- Test: `tests/unit/test_intent_integration.py`

**Step 1: Write the failing tests**

Add tests for:

1. `AdkDomainAgent.execute()` calls the intent integration stage after `before_execution(...)` and before `_execute_with_adk_runner(...)`
2. clarification returns `TaskResult(status=TaskStatus.PARTIAL, ...)` and does not call the runner
3. successful recognition writes the artifact to:
   - `agent_request.metadata["intent_recognition"]`
   - `agent_request.task_request.metadata["intent_recognition"]`
4. disabled pipeline leaves the existing execution path unchanged

Example test skeleton:

```python
@pytest.mark.asyncio
async def test_execute_short_circuits_when_intent_needs_clarification(monkeypatch):
    agent = AdkDomainAgent(agent_id="agent-1", config={})
    agent.runtime_context = {"intent_pipeline": fake_pipeline, "session_id": "sess-1"}

    called = False

    async def fake_runner(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(agent, "_execute_with_adk_runner", fake_runner)
    result = await agent.execute(agent_request)

    assert result.status == TaskStatus.PARTIAL
    assert called is False
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_adk_domain_agent_execution_paths.py tests/unit/test_intent_integration.py -v
```

Expected:

1. failure because the pre-LLM seam and short-circuit path do not exist yet

**Step 3: Write the minimal implementation**

Implementation rules:

1. add one explicit seam inside `AdkDomainAgent.execute()`
2. place it after `await self.hooks.before_execution(agent_request)`
3. place it before ADK tool rebuilding and before `_execute_with_adk_runner(agent_request)`
4. keep all decision logic inside `src/aether_frame/intent/integration.py`
5. do not redesign `AdkAgentHooks` in the MVP

Recommended integration helper shape:

```python
async def run_intent_stage(agent_request, runtime_context) -> IntentStageOutcome:
    ...
```

where the outcome is either:

1. `continue_execution` with an `IntentRecognitionResult`
2. `return_result` with a ready `TaskResult`

**Step 4: Run the tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_adk_domain_agent_execution_paths.py tests/unit/test_intent_integration.py -v
```

Expected:

1. all targeted tests pass

**Step 5: Commit**

```bash
git add src/aether_frame/agents/adk/adk_domain_agent.py src/aether_frame/intent/integration.py src/aether_frame/intent/default_pipeline.py tests/unit/test_adk_domain_agent_execution_paths.py tests/unit/test_intent_integration.py
git commit -m "feat: run intent recognition before main ADK execution"
```

### Phase 5: Verification and Rollout Safety

Outcome:

1. the feature is verified under both enabled and disabled modes
2. intent metadata is visible in result payloads and logs
3. rollout risk stays bounded

### Task 6: Add end-to-end verification coverage and rollout checks

**Files:**
- Create: `tests/integration/test_intent_recognition_flow.py`
- Modify: `docs/intent-recognition_design.md` only if implementation deviates from the design

**Step 1: Write the failing integration tests**

Add integration coverage for:

1. enabled pipeline recognized intent path
2. enabled pipeline clarification path
3. disabled pipeline pass-through path
4. LLM judgment disabled fallback path

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/integration/test_intent_recognition_flow.py -v
```

Expected:

1. failure because end-to-end intent flow coverage does not exist yet

**Step 3: Write the minimal implementation adjustments**

Only if the integration tests expose gaps:

1. fill missing metadata propagation
2. fill missing state-store cleanup
3. fill missing disabled-mode behavior

Do not expand scope into:

1. multi-turn orchestration beyond one clarification turn
2. catalog versioning
3. shared inference abstraction
4. context-layer redesign

**Step 4: Run the focused test suite**

Run:

```bash
uv run pytest \
  tests/unit/test_intent_contracts.py \
  tests/unit/test_intent_pipeline_noop.py \
  tests/unit/test_intent_pipeline.py \
  tests/unit/test_intent_state_store.py \
  tests/unit/test_intent_integration.py \
  tests/unit/test_bootstrap_flow.py \
  tests/unit/test_adk_domain_agent_execution_paths.py \
  tests/integration/test_intent_recognition_flow.py -v
```

Expected:

1. all intent-related tests pass

**Step 5: Run a broader regression subset**

Run:

```bash
uv run pytest \
  tests/unit/test_ai_assistant_unit.py \
  tests/unit/test_execution_engine_unit.py \
  tests/unit/test_adk_adapter_core.py \
  tests/unit/test_adk_agent_hooks.py -v
```

Expected:

1. existing core-path tests still pass

**Step 6: Commit**

```bash
git add tests/integration/test_intent_recognition_flow.py docs/intent-recognition_design.md
git commit -m "test: add intent recognition integration coverage"
```

## Delivery Criteria

The MVP is done when all of the following are true:

1. the external execution chain is unchanged
2. intent recognition runs inside `AdkDomainAgent.execute()` before the main ADK run
3. the pipeline is pluggable and can be disabled with settings
4. one clarification turn with 1 to 3 targeted questions returns `TaskStatus.PARTIAL` without reaching the main runner
5. `IntentRecognitionResult` is attached to metadata for downstream consumption
6. targeted unit and integration tests pass

## Deferred Until Post-MVP

Do not pull these into the MVP unless the implementation blocks without them:

1. `RuleOnlyIntentPipeline`
2. external catalog files
3. confidence calibration and score margins
4. shared model invocation abstraction
5. Redis or database-backed clarification state
6. more than one clarification turn
7. context-layer redesign beyond consuming the metadata artifact
