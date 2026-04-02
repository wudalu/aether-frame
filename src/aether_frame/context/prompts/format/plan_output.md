Return only a structured plan.

Plan requirements:

1. `plan_status` must accurately reflect feasibility.
2. `plan_summary` should describe the chosen path briefly.
3. `assumptions` must be explicit rather than hidden in prose.
4. `capability_gaps` must be listed whenever relevant.
5. each step must be explicit, actionable, and verifiable
6. each step must be executable with visible capabilities only
7. use `preferred_capability_ids` when one skill or capability is a better fit than others
8. include `verification_needed` or approval checkpoints for risky or write-like steps
9. avoid duplicate or overlapping steps
10. keep wording concrete enough that an executor can act without reinterpreting the goal

When clarification is required:

1. set `plan_status` to `needs_clarification`
2. ask only the minimum blocking questions

Do not include free-form narrative outside the expected structured output.
