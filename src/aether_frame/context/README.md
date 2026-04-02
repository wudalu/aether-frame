# Context Module

This package is the simplest home for model-visible call assembly.

Keep the split small:

1. `prompts/` stores reusable prompt fragments
2. `payloads/` stores structured dynamic inputs
3. `assembler.py` combines prompt fragments and payloads into one call

Recommended mental model:

1. `playbook runtime` decides the current phase and constraints
2. `context` decides what the current call should see
3. `skills/` still own reusable execution SOPs

In this simplified design, prompt fragments are part of the context layer rather than a separate top-level module.

Practical integration rule:

1. `planning` -> `base/system_core` + `phase/planning` + optional format or style + `planning_brief`
2. `execution` -> `base/system_core` + `phase/execution` + optional style + `current_step`
3. `evaluation` -> `base/system_core` + `phase/evaluation` + optional format or style + `review_package`
