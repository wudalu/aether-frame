# Intent Recognition Design for Aether Frame

Status: Proposed  
Date: 2026-03-18  
Scope: Add a pluggable intent-recognition chain inside the existing ADK execution path, before the main task LLM request, while keeping the current core request/response flow unchanged.

Cross references:
- `docs/research/2026-03-18-agent-intent-recognition.md`
- `docs/intent-registry-bootstrap_design.md`
- `docs/plans/2026-03-19-intent-recognition-mvp.md`
- `docs/architecture.md`
- `docs/flow.md`
- `docs/observability_plan.md`

## 1. Goal

The design goal is:

1. keep the current core execution flow unchanged
2. let the agent recognize user intent as the first execution-stage step
3. let intent recognition happen before the main task prompt/context is assembled
4. keep intent recognition pluggable
5. avoid large changes in existing core modules

The key boundary is:

1. `intent recognition` decides what the user is trying to do
2. `context layer` decides how to assemble the final context sent to the LLM

Intent recognition may produce an artifact that downstream layers consume, but it should not take over full context assembly.

## 2. Agreed Design Position

### 2.1 Core flow stays unchanged

The current core flow remains the system backbone:

```text
TaskRequest
  -> ExecutionEngine
  -> AdkFrameworkAdapter
  -> AgentRequest
  -> AdkDomainAgent
  -> ADK Runtime
```

This design does not add a new outer execution path in front of that chain.

### 2.2 Intent recognition happens inside the chain

Intent recognition should happen:

1. after `TaskRequest` already entered the normal execution flow
2. after `AgentRequest` exists
3. before the first main-task LLM request is sent

That means the agent sees the user request, runs intent recognition first, and only then proceeds to construct the final execution context.

### 2.3 Intent recognition is still pluggable

The whole intent-recognition chain should be pluggable behind one interface.

This plugin should be:

1. optional
2. replaceable
3. able to degrade to no-op
4. implemented in separate modules rather than spread across core files

### 2.4 Context assembly remains a separate concern

Intent recognition should output a structured artifact, for example:

1. intent label
2. extracted slots
3. missing slots
4. clarification requirement
5. execution hints

The later context layer should consume that artifact together with:

1. `TaskRequest`
2. session state
3. memory / knowledge
4. tool availability
5. other runtime signals

and then decide the final prompt/messages/context sent to the LLM.

### 2.5 Single-agent default, separate-agent optional

The design should distinguish:

1. the intent-layer contract
2. the runtime topology used to execute that contract

The contract should stay the same:

```text
input request
  -> IntentRecognitionPipeline
  -> IntentRecognitionResult
```

The default runtime topology should still be:

1. one logical agent
2. one execution spine
3. one in-chain pre-LLM intent stage

This remains the recommended MVP because it minimizes handoff overhead and preserves continuity with the existing execution path.

However, the design should not forbid a separate intent-specialized agent in the future.

A later implementation may choose:

1. `InProcessIntentPipeline`
   - runs inside the main agent before the main-task LLM call
2. `AgentBackedIntentPipeline`
   - calls a specialized intent agent and returns the same `IntentRecognitionResult`

This means the architecture should remain plugin-oriented, not topology-locked.

### 2.6 Artifact is additive, not a lossy replacement

If intent recognition is ever implemented as a separate agent or service, the downstream execution path should not receive only the structured artifact.

That would create the exact context-loss problem the design is trying to avoid.

The correct rule is:

1. `IntentRecognitionResult` is an additive artifact
2. it augments the downstream request context
3. it does not replace the original user request or relevant conversation state

So the downstream context layer should continue to consume:

1. the raw current user turn
2. relevant prior conversation turns
3. any clarification transcript produced by the intent layer
4. `IntentRecognitionResult`
5. normal session / memory / tool / knowledge inputs

This keeps the intent artifact useful without turning it into a lossy handoff boundary.

## 3. Review of the Research Note

The research note is a good design input, but not a repository-specific solution yet.

### 3.1 What is already solid

The research note gets the important principles right:

1. separate route intent, execution slots, and ambiguity handling
2. use structured output
3. treat low confidence and OOS as first-class outcomes
4. distinguish clarification from execution
5. prefer phased rollout over immediate automation

### 3.2 What it did not yet settle for Aether Frame

For this repository, the note did not yet fix these decisions:

| Gap | Why it matters here | Design response |
| --- | --- | --- |
| Where the logic should live | The repository already has a stable execution chain | Place intent recognition inside the existing chain, before the first main-task LLM request |
| Whether intent owns context assembly | That would conflict with later context engineering responsibilities | Intent outputs an artifact; context layer owns final assembly |
| Whether a new outer request flow is needed | That would create more structural change than necessary | Keep `TaskRequest -> ExecutionEngine -> AdkFrameworkAdapter -> AgentRequest -> AdkDomainAgent -> ADK Runtime` intact |
| How to avoid heavy edits in core modules | The repository treats ADK façade files as stable | Keep logic in separate `intent/` modules and add only minimal hook points |

### 3.3 Conclusion of the review

The research note remains valid, but for Aether Frame the design center should be:

1. in-chain intent recognition
2. artifact output
3. separate context assembly
4. minimal-touch integration

### 3.4 External best-practice evidence

As of 2026-03-19, current public guidance from major vendors and recent intent-recognition research points in the same direction as the design above.

| Source | External signal | Why it matters here |
| --- | --- | --- |
| [OpenAI, "A practical guide to building agents"](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/) | Recommends an incremental approach, maximizing single-agent capabilities first, and treating guardrails as critical across the workflow. | Supports keeping the existing single-agent execution spine and avoiding premature multi-agent decomposition. |
| [Claude, "Building multi-agent systems: When and how to use them"](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) | States that single-agent systems handle most enterprise workflows effectively, and that multi-agent systems add overhead and can lose context at handoff boundaries. | Supports the current decision to keep intent recognition inside one logical agent rather than splitting into two business agents. |
| [OpenAI Agents SDK: Context management](https://openai.github.io/openai-agents-python/context/) and [Anthropic, "Effective context engineering for AI agents"](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Distinguish local application context from model-visible context, and treat context curation as its own iterative discipline. | Supports the boundary where intent recognition emits a structured artifact while the context layer decides what becomes visible to the LLM. |
| [Google ADK, "Design Patterns and Best Practices for Callbacks"](https://github.com/google/adk-docs/blob/main/docs/callbacks/design-patterns-and-best-practices.md) | Supports inspecting, modifying, or short-circuiting model requests before execution, but explicitly recommends focused callbacks and avoiding long-running or blocking work inside them. | Supports adding one narrow pre-LLM seam while keeping the real intent logic in a separate module instead of building a monolithic callback. |
| [OpenAI Agents SDK: Guardrails](https://openai.github.io/openai-agents-python/guardrails/) | Input guardrails run on the initial user input and, in blocking mode, can prevent model and tool execution entirely. | Supports pre-main-task clarification or rejection before the expensive execution path continues. |
| [Arora et al., EMNLP 2024](https://aclanthology.org/2024.emnlp-industry.114/) and [den Hengst et al., NAACL 2024](https://aclanthology.org/2024.findings-naacl.156/) | Support hybrid intent routing, explicit uncertainty handling, targeted clarification, and OOS-aware recognition. | Supports the MVP choice of `HybridIntentPipeline`, one-turn clarification, and `unknown` / fallback outcomes. |

### 3.5 What this evidence means for Aether Frame

The current direction is correct, but only if implementation stays disciplined.

The evidence above implies these guardrails:

1. keep single-agent as the default operating model
2. keep intent output separate from final context assembly
3. keep the integration seam narrow and place the real logic in `src/aether_frame/intent/`
4. do not force an expensive LLM-based intent step on every request; prefer a cheap fast path and escalate only when needed
5. make clarification and fallback explicit first-class outcomes
6. define fail-open versus fail-closed behavior by execution risk
7. treat separate intent agents as an optional topology, not as the core contract
8. never let a structured intent artifact replace the raw request context

## 4. Target Runtime Chain

### 4.1 External system flow

The external flow remains:

```text
Frontend / API
  -> TaskRequest
  -> ExecutionEngine
  -> AdkFrameworkAdapter
  -> AgentRequest
  -> AdkDomainAgent
  -> ADK Runtime
```

### 4.2 Internal pre-LLM execution stages

Inside the agent/runtime path, the intended pre-LLM sequence becomes:

```text
TaskRequest
  -> ExecutionEngine
  -> AdkFrameworkAdapter
  -> AgentRequest
  -> AdkDomainAgent
      -> IntentRecognitionPipeline
          -> IntentRecognitionResult
      -> Context Layer
          -> consume TaskRequest + IntentRecognitionResult + session/memory/tools/knowledge
          -> assemble final LLM input
      -> ADK Runtime
          -> first main-task LLM call
```

### 4.3 Clarification branch

If intent recognition decides the request still needs clarification:

```text
TaskRequest
  -> ExecutionEngine
  -> AdkFrameworkAdapter
  -> AgentRequest
  -> AdkDomainAgent
      -> IntentRecognitionPipeline
          -> IntentRecognitionResult(needs_clarification=true)
      -> return TaskResult(status=PARTIAL, clarification_questions=[...])
```

In this branch:

1. the main task execution does not continue
2. the main-task context is not assembled yet
3. the clarification artifact is persisted for the next turn

### 4.4 Why this placement is correct

This placement satisfies the main concerns:

1. it keeps the current core flow intact
2. it lets the agent treat intent recognition as the first real execution step
3. it lets the intent layer reuse existing runtime/session/model capabilities
4. it avoids turning intent recognition into a second outer orchestration system

### 4.5 End-to-end execution flow

For the MVP, the intended execution flow should be read as a concrete sequence, not just a layering diagram.

Normal execution path:

1. frontend or API sends a normal user request and the system builds `TaskRequest`
2. `ExecutionEngine` selects the ADK path and forwards the request to `AdkFrameworkAdapter`
3. `AdkFrameworkAdapter` creates `AgentRequest` and prepares runtime context
4. `AdkFrameworkAdapter` injects the configured `intent_pipeline` and `intent_state_store` into the domain-agent runtime context
5. `AdkDomainAgent.execute()` starts and runs `hooks.before_execution(agent_request)`
6. before the main ADK runner call, `AdkDomainAgent.execute()` invokes one narrow pre-LLM intent seam
7. that seam calls the pluggable `IntentRecognitionPipeline`
8. the pipeline reads the current request, latest user message, session identity, and minimal runtime hints
9. the pipeline returns `IntentRecognitionResult`
10. the integration layer attaches that artifact to request metadata for downstream consumption
11. the later context layer uses `TaskRequest + IntentRecognitionResult + session/memory/tools/knowledge` to assemble the final model-visible context
12. `AdkDomainAgent` continues into `_execute_with_adk_runner(...)`
13. `ADK Runtime` performs the first main-task LLM call
14. normal execution completes and returns `TaskResult`

This is the intended MVP sequence:

```text
TaskRequest
  -> ExecutionEngine
  -> AdkFrameworkAdapter
      -> AgentRequest + runtime_context
      -> inject intent_pipeline / intent_state_store
  -> AdkDomainAgent.execute()
      -> hooks.before_execution(...)
      -> run_intent_stage(...)
          -> IntentRecognitionPipeline.recognize(...)
          -> IntentRecognitionResult
          -> attach artifact to metadata
      -> Context Layer
      -> _execute_with_adk_runner(...)
  -> TaskResult
```

### 4.6 Clarification and short-circuit flow

If the intent stage decides the request is still ambiguous, the execution flow should short-circuit before the main task LLM call.

Clarification path:

1. `run_intent_stage(...)` receives an `IntentRecognitionResult` with `needs_clarification=True`
2. the integration layer persists a small `PendingIntentState` keyed by `session_id`
3. the integration layer returns a ready `TaskResult(status=PARTIAL, ...)` with 1 to 3 targeted clarification questions
4. `AdkDomainAgent.execute()` returns that partial result immediately
5. `_execute_with_adk_runner(...)` is not called
6. the main-task context is not assembled
7. the main ADK model request does not happen on that turn
8. the next user turn can resume from the stored clarification state

```text
AdkDomainAgent.execute()
  -> hooks.before_execution(...)
  -> run_intent_stage(...)
      -> IntentRecognitionResult(needs_clarification=true)
      -> save PendingIntentState(session_id, prior_intent, clarification_turns=0)
      -> build TaskResult(status=PARTIAL, clarification_questions=[...])
  -> return TaskResult
```

This is the key behavioral contract:

1. clarification is a valid terminal outcome for the current turn
2. clarification happens before the expensive main-task execution path
3. the clarification result belongs to the intent layer
4. the final LLM context is only assembled after the request is clear enough to continue

### 4.7 MVP internal pipeline decision flow

Within the MVP `HybridIntentPipeline`, the expected internal flow is:

1. inspect the latest user request from `TaskRequest.description` and user messages
2. check whether there is pending clarification state for the current `session_id`
3. try a deterministic fast path against the small static MVP intent set
4. if the fast path is inconclusive and `intent_enable_llm_judgment=True`, run one optional low-cost structured LLM judgment step
5. normalize the final result into `IntentRecognitionResult`
6. choose one of three outcomes:
   - `continue`: request is understood well enough to proceed
   - `clarify`: request is ambiguous and needs 1 to 3 targeted questions
   - `fallback`: request is unsupported or remains unknown

This MVP decision loop should stay intentionally small:

```text
request
  -> deterministic fast path
      -> matched      -> continue
      -> ambiguous    -> optional LLM judgment
      -> unsupported  -> fallback
  -> optional LLM judgment
      -> clear enough -> continue
      -> still vague  -> clarify
      -> unsupported  -> fallback
```

The important design point is that the pipeline decides understanding outcomes, but it does not own final prompt assembly.

## 5. MVP Design

### 5.1 MVP principles

The MVP should stay small.

The MVP should:

1. support one pluggable pipeline interface
2. provide one production implementation and one no-op implementation
3. support at most one clarification turn
4. use a small static intent set
5. avoid embeddings
6. avoid external catalog loading
7. avoid large core refactors
8. prefer a cheap deterministic fast path before optional LLM judgment

### 5.2 MVP pipeline interface

```python
class IntentRecognitionPipeline(Protocol):
    async def recognize(
        self,
        agent_request: AgentRequest,
        runtime_context: Dict[str, Any],
    ) -> "IntentRecognitionResult":
        ...
```

This keeps the plugin focused on what it actually needs:

1. the current request
2. runtime/session information
3. access to already-normalized framework execution context

### 5.3 MVP result artifact

```python
class IntentRecognitionResult(BaseModel):
    intent: str
    confidence: Optional[float] = None
    slots: Dict[str, Any] = {}
    missing_slots: List[str] = []
    needs_clarification: bool = False
    clarification_questions: List[str] = []
    metadata: Dict[str, Any] = {}
```

This object is the output of the intent layer.

It is not:

1. the final prompt
2. the final context payload
3. a replacement for `TaskRequest`

It is simply the structured intent artifact that downstream layers consume.

If a future implementation runs intent recognition as a separate agent or external service, the handoff contract should still include more than this artifact.

The minimum safe handoff bundle should contain:

1. raw current user turn
2. relevant prior user and assistant turns
3. clarification transcript if the intent stage asked follow-up questions
4. `IntentRecognitionResult`
5. conversation or session identity

That bundle preserves enough context for the downstream context layer to continue without reconstructing meaning from the artifact alone.

#### 5.3.1 Optional handoff bundle for a separate intent agent

If the team later decides to run intent recognition as a separate specialized agent, the handoff contract should be explicit and loss-minimizing.

Recommended sketch:

```python
class ConversationTurn(BaseModel):
    role: Literal["user", "assistant", "system"]
    text: str
    created_at: Optional[str] = None


class IntentHandoffBundle(BaseModel):
    conversation_id: str
    session_id: Optional[str] = None
    current_user_turn: ConversationTurn
    prior_turns: List[ConversationTurn] = []
    clarification_turns: List[ConversationTurn] = []
    request_metadata: Dict[str, Any] = {}
```

This bundle is the minimum unit that should move across an agent boundary.

It should contain enough raw conversational context for:

1. the intent-specialized agent to make a good judgment
2. the downstream context layer to preserve continuity after the judgment is made

#### 5.3.2 Optional agent-backed pipeline sketch

The runtime-facing plugin contract should remain stable even if the internal implementation later changes from in-process logic to a separate intent agent.

Recommended sketch:

```python
class AgentBackedIntentPipeline(IntentRecognitionPipeline):
    async def recognize(
        self,
        agent_request: AgentRequest,
        runtime_context: Dict[str, Any],
    ) -> IntentRecognitionResult:
        handoff = self._build_handoff_bundle(agent_request, runtime_context)
        agent_response = await self._invoke_intent_agent(handoff)
        return self._normalize_agent_response(agent_response)
```

The important design rule is:

1. downstream code still consumes only `IntentRecognitionResult`
2. the extra cross-agent complexity is hidden inside the pipeline implementation
3. the main execution spine does not need to know whether intent recognition was in-process or agent-backed

#### 5.3.3 Recommended default versus optional topology

Recommended default:

```text
AdkDomainAgent
  -> InProcessIntentPipeline
  -> IntentRecognitionResult
  -> Context Layer
```

Optional later topology:

```text
AdkDomainAgent
  -> AgentBackedIntentPipeline
      -> IntentHandoffBundle
      -> intent-specialized agent
      -> IntentRecognitionResult
  -> Context Layer
```

The first topology is the recommended MVP.

The second topology is acceptable only if:

1. the handoff bundle keeps enough raw context
2. the team can justify the extra latency and observability complexity
3. the intent-specialized agent materially improves recognition quality or maintainability

### 5.4 Internal intent-layer execution flow

Inside the intent layer itself, the MVP should run as one small pipeline with explicit stages.

Recommended internal flow:

```text
AgentRequest + runtime_context
  -> request reader
      -> latest user text
      -> TaskRequest.description
      -> session_id
  -> pending-state lookup
      -> existing clarification state or none
  -> deterministic matcher
      -> matched / ambiguous / unsupported
  -> optional structured LLM classifier
      -> intent + slots + missing_slots + confidence
  -> outcome normalizer
      -> IntentRecognitionResult
  -> outcome handler
      -> continue / clarify / fallback
```

Stage responsibilities:

1. `request reader`
   - extracts the small request slice that intent recognition actually needs
   - avoids coupling the pipeline to full downstream context assembly
2. `pending-state lookup`
   - checks whether the current turn is answering a previous clarification
   - lets the pipeline merge the new user answer with prior intent state
3. `deterministic matcher`
   - handles obvious requests cheaply
   - classifies obvious unknowns without using LLM budget
4. `optional structured LLM classifier`
   - only runs when the fast path cannot decide well enough
   - returns typed fields, not free-form prompt text
5. `outcome normalizer`
   - converts raw matcher or classifier output into one stable result object
6. `outcome handler`
   - decides whether to continue execution, ask 1 to 3 clarification questions, or fall back

For the MVP, all of these stages can live inside `HybridIntentPipeline` private methods. They do not need to be split into many files yet.

### 5.5 What the intent layer needs to work

To build this system, the intent layer needs a small but complete set of inputs, policies, and runtime services.

Required request inputs:

1. latest user utterance
2. `TaskRequest.description`
3. `session_id`
4. request metadata, if there are already execution hints upstream

Required local configuration:

1. a small static intent registry
2. deterministic recognition rules or keyword heuristics for the fast path
3. clarification policy
4. fallback policy
5. feature flags for:
   - enable or disable intent recognition
   - select pipeline type
   - enable or disable optional LLM judgment
   - cap clarification questions per turn

Required runtime services:

1. `IntentRecognitionPipeline`
2. `IntentStateStore`
3. optional LLM classifier callable
4. integration helper that binds the result back onto request metadata

Required output contracts:

1. `IntentRecognitionResult`
2. `PendingIntentState`
3. an integration outcome that can represent:
   - continue execution
   - return clarification result now
   - return fallback result now if policy requires

### 5.6 Configuration preparation and user clarification

For the MVP, "configuration preparation" should be split into two different concerns.

The first concern is static system-side configuration.

This is prepared by the system at startup or bootstrap time and should include:

1. intent definitions
2. slot definitions
3. clarification rules
4. fallback rules
5. feature flags

Recommended MVP configuration shape:

```python
@dataclass
class SlotSpec:
    name: str
    required: bool = False
    description: str = ""
    clarification_question: str | None = None
    clarification_priority: int = 100


@dataclass
class IntentSpec:
    name: str
    description: str
    examples: list[str]
    required_slots: list[SlotSpec]
    optional_slots: list[SlotSpec]
```

For the MVP, this configuration can stay in code as a small static registry. It does not need an external catalog loader yet.

Recommended MVP source of this static configuration:

1. supported product capabilities already present in the system
   - existing task types
   - existing playbooks
   - existing skills and tool-enabled flows
2. representative user requests
   - product requirement examples
   - examples already present in docs and tests
   - real production traffic samples, if available
3. downstream execution requirements
   - what information the context layer or execution layer actually needs to proceed

Recommended MVP production workflow for the config:

1. start from 3 to 5 real supported user goals
2. define one `IntentSpec` per goal
3. define required and optional `SlotSpec` entries per intent
4. write 3 to 10 positive examples per intent
5. write a few confusing or negative examples for nearby intents
6. define a clarification question for each required slot that the system should not guess
7. review the spec with product or domain owners
8. store the result as Python constants in the repo
9. add fixture-based tests so the registry is evaluated, not just hand-authored

This gives you three practical ways to get the initial config:

1. hand-author it from your product understanding
   - recommended for MVP
2. scaffold it from existing playbook or skill definitions, then review manually
   - useful if your supported tasks are already well-structured
3. derive or refine it from historical user traffic and evaluation failures
   - better for post-MVP hardening than for the initial rollout

Recommended approach overall:

1. capability-constrained
2. traffic-informed
3. human-reviewed before promotion

For open-source accelerators, public datasets, and an offline bootstrap stack recommendation, see `docs/intent-registry-bootstrap_design.md`.

Do not build the first registry by clustering all user traffic and treating clusters as intents. That usually produces unstable categories, unsupported requests, and wording-based buckets that do not map cleanly to downstream execution.

Instead, use online traffic to refine and validate a capability-bounded registry.

Recommended workflow:

1. export representative request samples from production
   - request text
   - session_id
   - first user turn that started the task
   - final execution status
   - selected playbook, tool family, or downstream execution path if available
   - human escalation or clarification outcome if available
2. clean the sample set
   - remove or mask PII
   - deduplicate near-identical requests
   - sample by session, not just by raw row count
   - keep separate buckets for success, clarification, fallback, and failure
3. start from supported capabilities, not from traffic alone
   - list the 3 to 5 user goals the product truly supports today
   - use those as seed candidate intents
4. map traffic onto those seed intents
   - manually label a small but representative sample first
   - then use offline LLM summarization or clustering only to surface edge cases, near-duplicates, and missing candidate intents
5. derive slots from successful execution traces
   - inspect what information the execution path actually needed before it could proceed
   - promote only those recurring, execution-blocking fields into required slots
   - keep optional details out of the MVP slot set
6. define clarification questions from missing required slots
   - each required slot should have a direct question the system can ask when missing
   - add priority so the runtime can pick the top 1 to 3 questions
7. build the initial registry
   - `IntentSpec`
   - `SlotSpec`
   - positive examples
   - confusing negative examples
   - clarification priorities
8. validate offline before promotion
   - hold out a traffic slice the authors did not use when drafting the registry
   - measure intent match quality, clarification rate, fallback rate, and obvious confusion pairs
9. only promote intents that satisfy all of these:
   - meaningful request volume
   - clear downstream execution difference
   - stable wording patterns
   - acceptable offline precision on held-out traffic

Recommended use of LLMs in this workflow:

1. acceptable:
   - summarize clusters
   - propose candidate intent names
   - suggest slot candidates from successful traces
   - draft clarification questions
2. not acceptable:
   - auto-publish the registry without review
   - auto-create new production intents directly from one batch of traffic

This workflow yields a registry that is operationally useful, because every promoted intent is tied to an actual downstream execution path rather than to a semantic cluster only.

The second concern is runtime information completion from the user.

This is not system configuration. This is part of intent execution.

Yes, the intent layer should sometimes ask the user for more information, but only as a clarification step when:

1. a known intent has been recognized or narrowed enough
2. required slots are still missing
3. 1 to 3 short targeted questions can unblock execution
4. the system should not guess the missing business parameter

So the intended behavior is:

```text
static config prepared at startup
  -> request arrives
  -> intent matched against static config
  -> required slots checked
  -> if required slots missing
      -> select 1 to 3 highest-priority missing-slot questions
      -> return clarification questions to user
      -> persist PendingIntentState
  -> next user turn
      -> merge user answer with prior pending state
      -> re-run intent resolution
```

This means user questioning is part of the runtime clarification loop, not part of static configuration loading.

Recommended MVP clarification policy:

1. allow one clarification turn, but permit 1 to 3 questions inside that turn
2. ask only for execution-blocking missing slots
3. choose the highest-priority missing slots first
4. do not ask about optional slots in the MVP
5. if still unclear after one clarification turn, fall back instead of looping

The design implication is important:

1. bootstrap prepares intent specs and policies
2. runtime intent execution decides whether user input is still missing
3. `IntentStateStore` carries the gap across turns
4. context assembly only happens after enough information is available

### 5.7 MVP component set

For Aether Frame, the minimum useful component set is:

```text
src/aether_frame/intent/
  contracts.py
    - IntentRecognitionResult
    - PendingIntentState
    - IntentSpec
    - SlotSpec
  pipeline.py
    - IntentRecognitionPipeline
  registry.py
    - static MVP intent registry
  default_pipeline.py
    - NoOpIntentPipeline
    - HybridIntentPipeline
  state_store.py
    - InMemoryIntentStateStore
  integration.py
    - run_intent_stage(...)
    - attach_intent_artifact(...)
    - build_clarification_result(...)
```

What each part is for:

1. `contracts.py`
   - stable data boundary between intent layer and the rest of the system
2. `pipeline.py`
   - pluggable top-level interface
3. `registry.py`
   - source of truth for the MVP static intent and slot definitions
4. `default_pipeline.py`
   - actual MVP execution logic
5. `state_store.py`
   - carry one-turn clarification state across requests
6. `integration.py`
   - connect pipeline results to `AdkDomainAgent.execute()` without spreading logic into core files

### 5.8 MVP built-in implementations

Recommended initial implementations:

1. `NoOpIntentPipeline`
   - always returns a pass-through style result
   - used when intent recognition is disabled
2. `HybridIntentPipeline`
   - deterministic intent narrowing plus optional LLM judgment
   - production MVP default

Post-MVP, a `RuleOnlyIntentPipeline` can be added for testing and benchmarking.

### 5.9 MVP intent set

Keep the first intent set small.

Recommended size:

1. 3 to 5 intents maximum

Only include intents that can already influence downstream execution meaningfully.

Everything else should fall back to:

1. clarification
2. `unknown`
3. capability explanation

## 6. Responsibility Split

### 6.1 Intent layer responsibilities

The intent layer is responsible for:

1. understanding what the user wants to do
2. extracting key execution-relevant slots
3. identifying missing slots
4. deciding whether clarification is needed
5. returning a structured intent artifact

The intent layer is not responsible for:

1. final prompt assembly
2. final message selection
3. full context window composition
4. retrieval/memory orchestration beyond what intent classification itself needs

### 6.2 Context layer responsibilities

The context layer is responsible for:

1. consuming `TaskRequest`
2. consuming `IntentRecognitionResult`
3. incorporating session state and memory
4. selecting knowledge and tool scope
5. building the final input sent to the LLM

This is important because it keeps intent recognition useful but bounded.

## 7. Minimal-Touch Integration Strategy

### 7.1 Core rule

Keep almost all intent logic in new modules.

The intent feature should be implemented mostly under a separate package:

```text
src/aether_frame/intent/
  __init__.py
  contracts.py
  pipeline.py
  default_pipeline.py
  integration.py
  state_store.py
```

### 7.2 What core modules may change

Only small integration changes should be made in existing core files.

Recommended minimal touch points:

1. `src/aether_frame/bootstrap.py`
   - instantiate and wire the configured intent pipeline
2. `src/aether_frame/framework/adk/adk_adapter.py`
   - pass the pipeline or resolver handle into agent/runtime context
3. `src/aether_frame/agents/adk/adk_domain_agent.py`
   - add one pre-LLM integration call that invokes the separate intent module

The important rule is:

1. core files provide only the seam
2. the real logic lives in `src/aether_frame/intent/`

### 7.3 Preferred insertion seam

There is already a `before_execution` hook in `AdkAgentHooks`.

That gives two practical options:

1. preferred long-term seam: a formal pre-LLM hook path using hooks/integration helpers
2. MVP seam: one small explicit call in `AdkDomainAgent.execute()` before the first main-task model request

This is also consistent with current ADK guidance:

1. request inspection and short-circuiting before model execution are valid callback uses
2. monolithic or long-running callback logic is discouraged

So even if the seam eventually becomes a formal hook, the full intent-recognition chain should still live in dedicated modules rather than inside one heavyweight callback body.

For the MVP, option 2 is usually simpler because:

1. it allows short-circuiting to clarification cleanly
2. it avoids redesigning the generic hook contract
3. it still keeps all real intent logic outside the domain agent file

### 7.4 Why not modify the core more aggressively

That would create the wrong tradeoff:

1. more regression risk in stable execution files
2. more coupling between intent logic and ADK runtime details
3. harder future replacement of the intent chain

So the right shape is:

1. separate module for intent
2. one narrow seam into the existing execution lifecycle

## 8. Identity and State

Because intent recognition now runs inside the normal execution path:

1. `TaskRequest` already exists
2. `AgentRequest` already exists
3. runtime context and session information are normally available

This placement avoids the earlier problem where an outer intent layer might need to call LLMs before any execution session or agent had been created.

### 8.1 Pending clarification state

The MVP can keep a simple intent-specific state store:

```python
class PendingIntentState(BaseModel):
    session_id: str
    prior_intent: IntentRecognitionResult
    clarification_turns: int = 0
```

For the MVP:

1. in-memory storage is enough
2. max one clarification turn is enough
3. use existing session identity when available

## 9. Observability

For the MVP, keep observability minimal.

Recommended metadata:

1. `intent_name`
2. `needs_clarification`
3. `clarification_used`
4. `session_id`
5. `latency_ms`

Recommended locations:

1. `AgentRequest.metadata`
2. `TaskResult.metadata`
3. normal execution logs

Post-MVP, richer signals can be added:

1. candidate intents
2. confidence/margin
3. OOS bucket
4. should-have-clarified error slices

## 10. MVP Rollout

### Phase 0: MVP

Build:

1. `IntentRecognitionPipeline`
2. `NoOpIntentPipeline`
3. `HybridIntentPipeline`
4. `IntentRecognitionResult`
5. `PendingIntentState`
6. intent integration module
7. one narrow pre-LLM call site

Behavior:

1. core flow unchanged
2. one clarification turn maximum
3. static small intent set
4. intent artifact passed to context layer
5. context layer still owns final LLM input assembly

### Phase 1: hardening

Add:

1. better evaluation fixtures
2. richer logging and metrics
3. more robust clarification rules
4. optional externalized intent definitions

### Phase 2: richer pipeline internals

Add:

1. better candidate retrieval
2. richer scoring
3. optional rule-only implementation
4. more domain-specific intent families

### Phase 3: deeper architecture evolution

Only if justified later:

1. shared lower-level model invocation abstraction
2. dedicated retrieval infrastructure
3. more formal hook contracts

## 11. Testing Strategy

### 11.1 Unit tests

Recommended MVP tests:

1. `tests/unit/test_intent_pipeline.py`
2. `tests/unit/test_intent_pipeline_noop.py`
3. `tests/unit/test_intent_state_store.py`
4. `tests/unit/test_intent_integration.py`

### 11.2 Integration tests

Recommended MVP integration coverage:

1. request enters normal core flow and triggers intent recognition before main-task execution
2. clarification path returns partial result without continuing full execution
3. intent artifact is attached and visible to downstream context logic
4. disabled intent pipeline leaves existing behavior unchanged

### 11.3 E2E cases

Recommended MVP E2E cases:

1. direct recognized intent
2. one-turn clarification then execution
3. unknown intent fallback
4. disabled pipeline pass-through mode

## 12. Summary

The design should now be read as:

1. keep `TaskRequest -> ExecutionEngine -> AdkFrameworkAdapter -> AgentRequest -> AdkDomainAgent -> ADK Runtime` intact
2. insert a pluggable intent-recognition chain inside the agent pre-LLM stage
3. let that chain output `IntentRecognitionResult`
4. let the context layer, not the intent layer, own final context assembly
5. implement intent mostly in separate modules, with only a minimal seam added to core code

That gives Aether Frame an intent layer that is:

1. agent-first
2. pluggable
3. minimally invasive
4. compatible with future context-layer evolution
