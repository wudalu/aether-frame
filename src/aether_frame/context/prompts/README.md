# Prompts

This folder stores reusable prompt fragments used by the context layer.

Keep the structure simple:

1. `base/` for stable system prompt fragments
2. `phase/` for `planning`, `execution`, and `evaluation`
3. `format/` for output-shape instructions
4. `style/` for reusable response-style overlays
5. `domain/` for optional domain overlays
6. `playbook/` for optional playbook-specific overlays

Prompt design rules:

1. keep prompt fragments stable and reusable
2. keep dynamic task data in structured payloads, not hard-coded prose
3. make each phase prompt explicit about role, allowed reasoning scope, and failure handling
4. make format prompts explicit about output contracts
5. keep style and output-efficiency guidance separate from role prompts when possible
6. do not move runtime policy, approval logic, or hard validation into prompt text unless the model needs to be aware of the rule

The final prompt for one call should be assembled from a small subset of these files plus one structured payload.

Default phase mapping:

1. `planning` -> `base/system_core` + `phase/planning` + optional `format/plan_output` + optional `style/*` + `planning_brief`
2. `execution` -> `base/system_core` + `phase/execution` + optional `style/*` + `current_step`
3. `evaluation` -> `base/system_core` + `phase/evaluation` + optional `format/eval_decision` + optional `style/*` + `review_package`
