Return only a structured evaluation decision.

Include at minimum:

1. decision status
2. brief reason
3. hard failures or blockers when present
4. evidence references or explicit missing-evidence notes
5. next action hint when applicable
6. whether the issue is local to the current step or requires broader replanning

Prefer outputs that are easy for the runtime to map into:

1. `pass`
2. `retry`
3. `fallback`
4. `replan`
5. `block`
6. `fail`

Do not include long narrative outside the structured decision body.
