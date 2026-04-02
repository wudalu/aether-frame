# Phase Prompts and Skill Boundaries

Status: Working note  
Date: 2026-04-02  
Scope: Clarify how to organize concrete `planning`, `execution`, and `evaluation` prompts inside the context layer, and when to use prompts, skills, or runtime policy.

## 1. Why This Note Exists

Once `playbook runtime` and `context layer` are separated, a follow-up design question appears:

1. should `planning` have its own prompt?
2. should `evaluation` have its own prompt?
3. should those become standalone skills instead?

The short answer is:

1. yes, each phase can have its own prompt fragment
2. no, that does not automatically mean each phase should become a skill
3. skills are better for reusable execution SOPs than for every phase role

## 2. Recommended Default

Use the following default split:

1. `planning` -> phase-specific prompt + structured planning contract
2. `step execution` -> execution prompt + current-step payload + optional skill
3. `reflection/evaluation` -> evaluation prompt + review contract
4. runtime guards -> approval, schema validation, budgets, and tool policy outside the prompt

This keeps the architecture clean:

1. prompt fragments define role and behavior expectations for one call
2. `skills` define reusable how-to execution routines
3. `runtime policy` defines what is allowed, blocked, retried, or escalated

## 3. Decision Rule: Prompt vs Skill vs Runtime Policy

### 3.1 Use a Prompt Fragment When

The main job is to shape one model call:

1. define the role for the current phase
2. define how the model should think or judge
3. define output format or style
4. define semantic priorities for one call

Examples:

1. planner role prompt
2. evaluator role prompt
3. concise answer formatter
4. domain-specific answer discipline

### 3.2 Use a Skill When

The main job is to reuse a bounded execution SOP:

1. multiple steps recur across tasks
2. the routine uses tools in a repeatable way
3. retries, fallbacks, or normalization belong to that routine
4. the result should be versioned and tested as a reusable capability

Examples:

1. research synthesis
2. summary rewrite
3. code change verification flow
4. citation verification routine with tool orchestration

### 3.3 Use Runtime Policy When

The rule should be enforced whether or not the model follows instructions:

1. approval gates
2. tool allowlists
3. budget limits
4. schema validation
5. retry ceilings
6. high-risk side-effect blocking

These should not rely on prompt obedience alone.

## 4. Phase-by-Phase Recommendation

### 4.1 Planning

Default recommendation: prompt, not skill.

Reason:

1. planning is primarily a reasoning role
2. its main input is a structured brief such as `planning_brief`
3. its main output is a structured plan such as `plan_output`

Upgrade planning into a skill only if it grows into a reusable multi-step routine of its own, for example:

1. repo inspection before plan drafting
2. fixed risk-check substeps
3. deterministic pre-plan artifact collection

### 4.2 Step Execution

Default recommendation: combine prompt and skill.

Reason:

1. execution still needs an operator role prompt
2. but execution is where reusable SOPs matter most
3. this is the natural place to call skills

Typical pattern:

1. `execution` prompt
2. `current_step` payload
3. selected `skill`
4. whitelisted tools

### 4.3 Reflection and Evaluation

Default recommendation: prompt, not skill.

Reason:

1. evaluation is usually a judge or gate role
2. the core input is a review package, not an open-ended task
3. output is a decision such as `pass`, `retry`, `replan`, or `block`

Upgrade evaluation into a skill only when the review itself becomes a reusable execution routine, for example:

1. citation validator that fetches sources
2. compliance reviewer with fixed external checks
3. regression checker that runs known validations

## 5. Practical Rule of Thumb

Use this quick test:

```text
Is this mainly about how one call should behave?
  -> prompt fragment

Is this mainly about how to repeatedly perform a bounded job?
  -> skill

Must this be enforced even if the model ignores it?
  -> runtime policy
```

## 6. Example Combination

One task may use all three layers at once:

```text
phase = execute_step
  prompt: execution role + output format
  skill: summary_rewrite
  runtime policy: write disabled, max 1 tool call, schema required
```

That is why these layers should stay separate. They solve different problems.

## 7. Simplest Prompt Organization

The simplest approach is to keep concrete prompts inside the context layer instead of creating a separate top-level `instructions/` module.

Recommended directory:

```text
src/aether_frame/context/
  __init__.py
  README.md
  assembler.py
  payloads/
    __init__.py
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
    domain/
      ...
    playbook/
      ...
```

### 7.1 Directory Intent

1. `prompts/base`
   - stable system prompt fragment
2. `prompts/phase`
   - concrete prompts for `planning`, `execution`, and `evaluation`
3. `prompts/format`
   - output-shape prompt fragments
4. `prompts/style`
   - reusable style overlays such as concise operational output
5. `prompts/domain`
   - optional domain overlays
6. `prompts/playbook`
   - optional playbook-specific overlays
6. `payloads`
   - dynamic task data such as `planning_brief`, `current_step`, and `review_package`
7. `assembler.py`
   - combines prompt fragments and payloads into one bounded call

## 8. Boundary with Existing `skills/`

The repository already has `src/aether_frame/skills/` for reusable SOPs. Keep that split:

1. `context/prompts/` tells the model how to behave in a phase
2. `skills/` package reusable execution routines

Do not move existing skills into `context/prompts/`.

## 9. Design Rule

Use this final rule when in doubt:

```text
prompts shape the current call
skills package routines
runtime policy enforces boundaries
```

## Related Docs

- `docs/plans/2026-04-02-context-prompt-integration.md`
- `docs/plans/2026-04-02-playbook-runtime-context-layering.md`
- `docs/plans/adk-skill-integration-design.md`
- `docs/roadmaps/context_engineering_org.md`
