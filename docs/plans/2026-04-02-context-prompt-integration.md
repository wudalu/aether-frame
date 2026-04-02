# Integrating Prompt Fragments Into Context Assembly

Status: Working note  
Date: 2026-04-02  
Scope: Explain how prompt fragments under `src/aether_frame/context/prompts/` should be integrated into the context layer for `planning`, `execution`, and `evaluation` calls.

## 1. Why This Note Exists

The repository now has a simple prompt-layer layout:

1. stable prompt fragments under `context/prompts/`
2. dynamic per-call payloads under `context/payloads/`
3. a reserved assembly entrypoint in `context/assembler.py`

What was still easy to miss was the integration rule:

1. which prompt fragments should be used for each phase
2. which inputs belong in payloads instead of prompt text
3. how `playbook runtime` state should drive prompt selection

This note defines that assembly contract.

## 2. Assembly Goal

The goal is not to build one ever-growing prompt.

The goal is to build one bounded phase-specific model call from:

1. a small prompt set
2. one structured payload
3. selected evidence, artifacts, and history
4. runtime-visible constraints that the model needs to know about

The integration rule is:

```text
playbook runtime chooses the phase
  -> context layer chooses prompt fragments and payload contract
  -> assembler renders one bounded model-visible request
```

## 3. Responsibility Split

### 3.1 Playbook Runtime

`playbook runtime` decides:

1. the active phase
2. the current step or review target
3. whether the next call is `planning`, `execution`, or `evaluation`
4. which capabilities, approvals, and checks are visible for the next call

It should emit control state such as a `PhaseFrame`, not write final prompt text.

### 3.2 Context Layer

`context layer` decides:

1. which prompt fragments are relevant for the current phase
2. which payload contract should be rendered
3. which evidence and artifact references are worth including
4. how the final request is serialized for the model SDK

### 3.3 Prompt Fragments

Prompt fragments should hold stable model-facing behavior instructions:

1. `base` for the stable system core
2. `phase` for `planning`, `execution`, and `evaluation`
3. `format` for output-shape requirements
4. `style` for reusable response-style overlays
5. optional `domain` overlays
6. optional `playbook` overlays

Prompt fragments should not become a storage place for dynamic task data.

### 3.4 Payloads

Payloads should hold dynamic task data such as:

1. `planning_brief`
2. `current_step`
3. `review_package`

Payloads should carry current task state, not reusable behavior rules.

## 4. Directory Contract

The current minimal structure is:

```text
src/aether_frame/context/
  README.md
  assembler.py
  payloads/
    README.md
  prompts/
    README.md
    base/
      system_core.md
    phase/
      planning.md
      execution.md
      evaluation.md
    format/
      plan_output.md
      eval_decision.md
    style/
      output_efficiency.md
```

The intended meaning of each part is:

1. `prompts/base/system_core.md`
   - stable role, operating discipline, and durable model-facing rules
2. `prompts/phase/*.md`
   - what the model should do in the current phase
3. `prompts/format/*.md`
   - output-shape constraints for that phase
4. `prompts/style/*.md`
   - reusable tone or brevity overlays
5. `payloads/*`
   - structured current-task inputs
6. `assembler.py`
   - the place that combines the selected prompt fragments and rendered payload into one model call

## 5. Phase-to-Prompt Mapping

The simplest recommended mapping is below.

### 5.1 Planning Call

Use this prompt stack:

1. `base/system_core.md`
2. `phase/planning.md`
3. optional `style/output_efficiency.md`
4. optional `format/plan_output.md`
5. optional `playbook/<playbook_id>/planning.md`
6. optional `domain/<domain_id>.md`

Use this payload contract:

1. `planning_brief`

Recommended `planning_brief` ingredients:

1. normalized goal and user intent
2. intent artifact fields
3. playbook policy view and success criteria
4. visible capability or skill inventory
5. execution constraints
6. selected prior evidence if it matters for replanning

Important rule:

- the planner should usually see skill metadata and capability summaries, not full skill SOP bodies

### 5.2 Execution Call

Use this prompt stack:

1. `base/system_core.md`
2. `phase/execution.md`
3. optional `style/output_efficiency.md`
4. optional `playbook/<playbook_id>/execution.md`
5. optional `domain/<domain_id>.md`

Use this payload contract:

1. `current_step`

Recommended `current_step` ingredients:

1. step objective
2. completion check
3. allowed capabilities
4. selected skill ids or capability ids
5. approval or write visibility that the model needs to respect
6. relevant artifacts and evidence only for this step

Important rule:

- execution is where a selected skill may be loaded or referenced as the preferred SOP

### 5.3 Evaluation Call

Use this prompt stack:

1. `base/system_core.md`
2. `phase/evaluation.md`
3. optional `style/output_efficiency.md`
4. optional `format/eval_decision.md`
5. optional `playbook/<playbook_id>/evaluation.md`
6. optional `domain/<domain_id>.md`

Use this payload contract:

1. `review_package`

Recommended `review_package` ingredients:

1. candidate output or step result
2. acceptance criteria
3. evidence and artifact references
4. relevant runtime policy summary
5. plan or step summary only if needed for judgment

Important rule:

- evaluation should judge the current candidate with evidence, not regenerate the whole task

## 6. Minimal Assembly Rules

The context layer should use these rules when assembling one call:

1. always include the stable system core
2. include exactly one phase prompt for the active phase
3. include one payload contract for the active phase
4. include format overlays only when the phase needs a bounded output schema
5. include style overlays only when they do not conflict with the phase contract
6. include playbook or domain overlays only when they add real specialization
7. keep runtime-only policy outside prompt text unless the model must see it

This gives a simple ordering model:

```text
base
  -> phase
  -> optional playbook/domain
  -> optional format/style
  -> rendered payload
  -> selected evidence and artifacts
```

## 7. What Must Stay Out of Prompt Fragments

Do not use prompt fragments to store:

1. changing retry counters
2. raw execution logs
3. approval state that changes every turn unless the model must see it
4. full conversation history by default
5. hard enforcement rules that belong in runtime policy

Examples of runtime-policy responsibilities:

1. tool allowlists
2. budget ceilings
3. schema validation
4. block-on-write gates
5. retry ceilings

The model can be informed of relevant boundaries, but the boundaries themselves should still be enforced outside the prompt.

## 8. Minimal Assembler Flow

The intended flow for `assembler.py` is:

```python
def build_call(phase_frame, state, prompt_store, payload_store):
    phase = phase_frame.phase

    prompt_ids = ["base/system_core", f"phase/{phase}"]

    if phase == "planning":
        prompt_ids.append("format/plan_output")
        payload = payload_store.render_planning_brief(state, phase_frame)
    elif phase == "execution":
        payload = payload_store.render_current_step(state, phase_frame)
    elif phase == "evaluation":
        prompt_ids.append("format/eval_decision")
        payload = payload_store.render_review_package(state, phase_frame)
    else:
        raise ValueError(f"Unsupported phase: {phase}")

    if state.style_overlays:
        prompt_ids.extend(state.style_overlays)

    if state.active_playbook_overlay:
        prompt_ids.append(state.active_playbook_overlay.for_phase(phase))

    prompt_text = prompt_store.render(prompt_ids)
    evidence = select_relevant_evidence(state, phase_frame)

    return {
        "system_prompt": prompt_text,
        "payload": payload,
        "evidence": evidence,
    }
```

This pseudocode intentionally stays minimal. The main point is the contract:

1. phase chooses the prompt family
2. payload renderer chooses the structured input
3. assembler joins both into one bounded call

## 9. Practical Design Rules

Use these rules when adding new prompt fragments later:

1. if the text explains stable behavior, it belongs in `prompts/`
2. if the text describes current task data, it belongs in a payload renderer
3. if the rule must hold even when the model ignores instructions, it belongs in runtime policy
4. if the capability is a reusable execution routine, it belongs in `skills/`, not prompt fragments

## 10. Near-Term Implementation Path

The next practical steps are:

1. keep the current prompt fragment set small and reusable
2. define typed renderers for `planning_brief`, `current_step`, and `review_package`
3. implement a first `assembler.py` that resolves prompt ids by phase
4. add optional playbook overlays only when a playbook truly needs them
5. leave `domain/` empty until a real domain split is stable

## Related Docs

- `docs/plans/2026-04-02-playbook-runtime-context-layering.md`
- `docs/plans/2026-04-02-instruction-layering-and-skill-boundaries.md`
- `docs/roadmaps/context_engineering_org.md`
- `src/aether_frame/context/README.md`
