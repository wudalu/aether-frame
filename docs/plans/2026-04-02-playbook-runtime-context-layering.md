# Playbook Runtime, Context Layer, and Instruction Layering

Status: Working note  
Date: 2026-04-02  
Scope: Clarify how `playbook runtime`, `context layer`, and different instruction levels work together in one agent run.

## 1. Why This Note Exists

These concepts are easy to mix together:

1. `playbook runtime`
2. `context layer`
3. prompt fragments inside the context layer
4. the final prompt or model request

They are related, but they are not the same thing.

The key distinction is:

1. `playbook runtime` controls the task flow
2. `context layer` assembles one phase-specific call
3. prompt fragments provide reusable model-visible guidance
4. the final prompt is only the rendered output of that assembly

## 2. Core Responsibility Split

### 2.1 Playbook Runtime

`Playbook runtime` is the control plane.

It should behave like a stateful orchestrator:

1. track the current phase
2. decide what kind of step comes next
3. decide whether the next action is `plan`, `execute`, `reflect`, `replan`, `block`, or `finish`
4. enforce gating such as approval, retry budget, and required checks
5. update state from step results and evidence

Important: `playbook runtime` should not be the place that writes long prompt text.

Its output should be control semantics, for example:

```json
{
  "phase": "reflect_step",
  "step_id": "S2",
  "llm_role": "evaluator",
  "allowed_capabilities": ["validate", "reflect"],
  "required_checks": ["schema_valid", "evidence_present"],
  "retry_budget_remaining": 1,
  "next_on_pass": "execute_step:S3",
  "next_on_fail": "replan"
}
```

This is an internal runtime decision object, not user-facing text.

### 2.2 Context Layer

`Context layer` is the assembly plane.

It consumes runtime state and builds the exact input for one call:

1. selects the relevant prompt fragments
2. selects the relevant task payload
3. selects the relevant memory, artifacts, and evidence
4. trims and orders them into a bounded `context pack`
5. renders the model-visible request

The context layer does not decide the workflow. It materializes the current workflow decision into one concrete call.

### 2.3 Prompt Fragments

The context layer can still organize prompt content by scope, but this should stay an internal part of context assembly rather than a separate top-level system.

Typical fragment groups:

1. `base` system prompt fragments
2. `phase` fragments such as `planning`, `execution`, and `evaluation`
3. optional `domain` fragments
4. optional `playbook` fragments
5. optional `format` fragments

Not every rule should become prompt text. Approval gates, tool allowlists, budgets, and schema checks should remain runtime policy.

## 3. Relationship Model

The recommended relationship is:

```text
user request
  -> route/select playbook
  -> playbook runtime enters a phase
  -> runtime emits a phase frame
  -> context layer selects applicable prompt fragments
  -> context layer builds a context pack
  -> context layer renders model-visible input
  -> LLM/tool call runs
  -> result + evidence return
  -> playbook runtime updates state and decides the next transition
```

This means:

1. the runtime decides "what the system is trying to do next"
2. the context layer decides "what this specific call needs to see"
3. the renderer decides "how that input is encoded for the current model SDK"

## 4. Recommended Data Objects

The cleanest mental model is to separate runtime state from call input.

### 4.1 `PlaybookState`

Longer-lived run state:

1. `playbook_id`
2. `phase`
3. `plan`
4. `current_step_id`
5. `artifacts`
6. `evidence`
7. `retry_counts`
8. `approval_state`

### 4.2 `PhaseFrame`

The runtime output for one transition:

1. `phase`
2. `step_id`
3. `llm_role`
4. `allowed_capabilities`
5. `required_checks`
6. `required_state`
7. `transition_options`

### 4.3 `PromptSet`

The resolved prompt fragments for one call:

1. stable system prompt fragment
2. current phase prompt fragment
3. optional domain or playbook prompt fragment
4. optional output-format prompt fragment

### 4.4 `ContextPack`

The bounded payload for one call:

1. rendered prompt fragments
2. structured task payload such as `planning_brief`, `current_step`, or `review_package`
3. selected history
4. selected evidence and artifact references
5. tool manifest and schema requirements

### 4.5 `TransitionDecision`

The result of the current step evaluation:

1. `pass`
2. `retry`
3. `fallback`
4. `replan`
5. `block`
6. `fail`

## 5. How the Main Loop Works

The runtime is best understood as a state machine with bounded loops:

```text
PLAN
  -> EXECUTE_STEP
  -> REFLECT_STEP
     -> pass     -> EXECUTE_STEP(next)
     -> retry    -> EXECUTE_STEP(same)
     -> fallback -> EXECUTE_STEP(modified)
     -> replan   -> PLAN
     -> block    -> HUMAN
  -> FINAL_EVALUATION
     -> pass     -> FINAL_ANSWER
     -> replan   -> PLAN
     -> block    -> HUMAN
```

Recommended pseudocode:

```python
def run_playbook(request):
    state = init_playbook_state(request)

    while True:
        frame = playbook_runtime.next_frame(state)
        prompt_set = context_layer.resolve_prompts(state, frame)
        context_pack = context_layer.build(state, frame, prompt_set)

        if frame.phase == "plan":
            plan = planner(context_pack)
            state = playbook_runtime.apply_plan(state, plan)
            continue

        if frame.phase == "execute_step":
            step_result = executor(context_pack)
            state = playbook_runtime.record_step_result(state, step_result)
            continue

        if frame.phase in {"reflect_step", "final_evaluation"}:
            decision = evaluator(context_pack)
            state = playbook_runtime.apply_decision(state, decision)

            if decision.status == "pass" and state.is_finished:
                return finalizer.build_user_answer(state)
            if decision.status == "block":
                return human_gate_response(state, decision)
            if decision.status == "fail":
                return failure_response(state, decision)

            continue
```

The important point is that the runtime loop decides transitions, while the context layer builds inputs for the individual planner, executor, and evaluator calls inside that loop.

## 6. What Should and Should Not Go Into System Prompt

Good candidates for stable `system prompt` content:

1. role and identity
2. long-lived safety or compliance rules
3. general operating discipline
4. durable answer-style expectations

Better kept outside the stable `system prompt`:

1. current step payload
2. current evidence set
3. temporary retry counters
4. dynamic approval state
5. most plan and review contracts

## Related Docs

- `docs/plans/2026-04-02-context-prompt-integration.md`
- `docs/plans/2026-04-02-instruction-layering-and-skill-boundaries.md`
- `docs/roadmaps/context_engineering_org.md`

Those belong in structured phase payloads or runtime policy objects, not in one ever-growing prompt.

## 7. Design Rule

Use this rule when deciding where something belongs:

1. If it controls workflow state, it belongs to `playbook runtime`.
2. If it controls what one call should see, it belongs to `context layer`.
3. If it is reusable model-visible guidance, it belongs to context-layer prompt fragments.
4. If it is only one transport format for the model, it belongs to context rendering.

In short:

```text
runtime decides
context assembles
context renders
model executes
```

## 8. Related Docs

- `docs/plans/2026-03-13-playbook-orchestration-design.md`
- `docs/plans/2026-03-05-reflection-acceptance-criteria-design.md`
- `docs/plans/2026-04-02-instruction-layering-and-skill-boundaries.md`
- `docs/roadmaps/context_engineering_org.md`
- `docs/roadmaps/agent_system_one_page.md`
