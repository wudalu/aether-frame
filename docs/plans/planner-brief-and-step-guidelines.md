# Planner Brief and Step Design Guidelines

Status: Working note  
Scope: Define the default input contract for `planner` and the recommended shape for user-visible plan steps.

## 1. Recommended Default

Use a four-layer split by default:

1. `plan`
   - user-visible subgoals
2. `execution`
   - lower the current step into `skill`, `tool`, or subagent calls
3. `control`
   - run `verify -> pass / retry / replan / block / ask-human`
4. `response`
   - produce the final answer or an explicit deliverable step only

Design rules:

1. a plan step is a verifiable subgoal, not a tool call
2. `tool` and `skill` are execution means, not the primary plan language
3. keep raw chain-of-thought out of persisted plans
4. if reasoning must be retained, keep a short `reasoning_summary` only
5. make `verify`, `replan`, and `approval` first-class runtime decisions

## 2. Required Planner Input

The planner should receive one structured `planning_brief`, not a raw conversation dump.

Minimum required fields:

1. `goal`
   - the normalized target state
2. `deliverables`
   - what the task must produce, such as answer, report, code change, test result, or artifact
3. `current_state`
   - known facts, completed work, failed attempts, and currently available evidence
4. `capability_inventory`
   - visible tools, skills, and other allowed execution mechanisms
5. `constraints`
   - time, budget, permissions, environment, network, write access, and other hard boundaries
6. `success_criteria`
   - what counts as done

Recommended additional fields:

1. `verification_contract`
   - step-level and final checks, with preferred evidence sources
2. `ambiguities_or_gaps`
   - missing prerequisites, unresolved questions, and allowed assumptions
3. `prior_evidence`
   - only the evidence that matters for initial planning or bounded replanning

Example:

```json
{
  "goal": "Locate and fix the login failure",
  "deliverables": ["code change", "test evidence", "change summary"],
  "current_state": {
    "known_facts": ["users see HTTP 500 on login"],
    "completed_steps": [],
    "failed_attempts": [],
    "evidence_refs": ["log:auth-500"]
  },
  "capability_inventory": [
    {"id": "shell", "type": "tool"},
    {"id": "apply_patch", "type": "tool"},
    {"id": "systematic_debugging", "type": "skill"}
  ],
  "constraints": {
    "network": false,
    "write_allowed": true
  },
  "success_criteria": [
    "root cause is identified",
    "fix is minimal",
    "relevant tests pass"
  ],
  "verification_contract": {
    "step_level": ["logs", "tool output", "tests", "diff"],
    "final": ["all deliverables present"]
  },
  "ambiguities_or_gaps": [
    "reproduction path is not fully confirmed"
  ]
}
```

## 3. Recommended Plan Step Contract

The planner should output steps as subgoals with explicit checks.

```ts
type PlanStep = {
  id: string
  title: string
  objective: string
  depends_on?: string[]
  preconditions?: string[]
  preferred_capabilities?: string[]
  completion_check: string[]
  expected_evidence: string[]
  risk_level?: "low" | "medium" | "high"
  approval_required?: boolean
  on_failure: "retry" | "fallback" | "replan" | "block"
}
```

Step-writing rules:

1. write each step in subgoal language, not action language
2. do not encode `thinking`, `tool_call`, or `response` as normal business steps
3. include enough detail that an executor can act without redefining the task
4. keep steps minimal but dependency-aware

Bad:

1. `run rg`
2. `call pytest`
3. `apply patch`
4. `respond`

Good:

1. identify the failure mechanism; completion check: root-cause evidence captured
2. implement the smallest valid fix; completion check: code change matches the diagnosis
3. verify the fix; completion check: relevant checks pass
4. summarize outcome and residual risk; completion check: final deliverables are complete

## 4. Runtime Trace Model

Keep execution details in trace items instead of the plan itself.

Recommended trace item types:

1. `reasoning_summary`
2. `tool_call`
3. `skill_call`
4. `observation`
5. `verification`
6. `approval_request`
7. `replan`
8. `final_answer`

This keeps:

1. the plan stable
2. execution auditable
3. reasoning bounded
4. replanning easier when the world state changes

## 5. Naming Note

New docs in `docs/plans/` should use stable filenames without date prefixes.

Preferred:

1. `planner-brief-and-step-guidelines.md`
2. `playbook-runtime-context-layering.md`

Avoid for new files:

1. `2026-04-02-some-note.md`

## Related Docs

- `docs/plans/2026-03-13-playbook-orchestration-design.md`
- `docs/plans/2026-04-02-context-prompt-integration.md`
- `docs/plans/2026-04-02-instruction-layering-and-skill-boundaries.md`
