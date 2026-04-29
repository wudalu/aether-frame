# Final User Summary Prompt

Status: Template  
Scope: Direct-use prompt for generating concise, user-facing final summaries after an agent task.

## 1. Purpose

Use this prompt at the finalization step of an agent workflow, after the agent has completed work or reached a clear stopping point.

This prompt is intentionally narrower than a handoff summary or context-compaction summary. It is for the user-facing final answer only.

Use it when the model needs to summarize:

1. what outcome was achieved
2. what concrete work was completed
3. what validation or evidence exists
4. what limitations remain
5. what next step, if any, is directly useful

For broader summary modes, see `docs/agent_summary_prompt_template.md`.

## 2. Direct-Use Prompt

```text
You are generating the final user-facing summary for an agent task.

Your job is to explain the final outcome clearly and concisely based only on the provided task context, completed work, evidence, artifacts, validation, and known limitations.

INPUTS:
<user_request>
{user_request}
</user_request>

<completed_work>
{completed_work}
</completed_work>

<evidence>
{evidence}
</evidence>

<artifacts>
{artifacts}
</artifacts>

<validation>
{validation}
</validation>

<known_limitations>
{known_limitations}
</known_limitations>

RULES:
1. Lead with the outcome, not the process.
2. Only state facts supported by the inputs.
3. Clearly distinguish completed work, verified work, limitations, and next steps.
4. Do not expose hidden reasoning, internal chain-of-thought, raw tool logs, or irrelevant implementation details.
5. Do not claim tests, checks, citations, or validation passed unless they are explicitly present in <validation>.
6. If the task is incomplete or blocked, say so directly and explain what is missing.
7. If artifacts, files, URLs, source IDs, or artifact URIs are provided, reference only the important ones.
8. Do not ask follow-up questions unless the final answer would be misleading without one.

LENGTH AND DETAIL POLICY:
Adjust the length to the amount of meaningful user-facing information available.

- If the work is simple or only one change/result matters, write one short paragraph.
- If there are several concrete outcomes, use one short paragraph plus up to three compact bullets.
- If validation, limitations, or references materially affect the user's decision, include those sections briefly.
- If the prior context contains long tool logs, repeated attempts, intermediate reasoning, or low-value implementation details, compress them aggressively or omit them.
- Preserve only details that help the user understand the outcome, trust the result, or decide the next step.
- Prefer concise synthesis over chronological narration.
- Do not expand the summary just because the task history is long.

OUTPUT FORMAT:
Use Markdown.

Start with a short paragraph summarizing the final outcome.

Then include only the sections that are useful:

**What Was Done**
- List the concrete completed work.

**Validation**
- Mention tests, checks, review, or evidence that were actually run or provided.
- If no validation was run, say: "Validation was not run."

**Limitations**
- Mention known caveats, blockers, missing inputs, or uncertainty.
- Omit this section if there are no known limitations.

**References**
- List important files, artifact URIs, source IDs, or URLs.
- Omit this section if there are no references.

**Next Step**
- Include one concrete next step only if it is directly relevant.
- Omit this section if no next step is needed.
```

## 3. Minimal Runtime Inputs

At minimum, provide these fields:

1. `user_request`: the user's original request or normalized task goal
2. `completed_work`: concise list of completed actions or deliverables
3. `validation`: tests, checks, review evidence, citations, or `not_run`
4. `known_limitations`: blockers, uncertainty, missing input, or `none`

Optional but recommended:

1. `evidence`: short evidence summaries with stable IDs
2. `artifacts`: files, URLs, or `artifact://` URIs

## 4. Expected Behavior

The generated final answer should usually look like this:

```text
The requested documentation was added as a focused final-summary prompt template, with guidance for concise user-facing outcomes and content-aware detail selection.

**What Was Done**
- Added `docs/final_user_summary_prompt.md` with a direct-use prompt and runtime input guidance.

**Validation**
- Checked that the new document exists and includes the expected prompt sections.
```

For very small tasks, the output can be a single paragraph:

```text
The requested wording was added to the final summary prompt. It now asks the model to keep the answer concise based on the amount of meaningful user-facing information, without imposing a hard word limit.
```

## 5. Integration Notes

Recommended placement in the context assembly layer:

1. stable behavior -> summary prompt fragment
2. dynamic task data -> payload fields
3. raw tool output -> Artifact Store, referenced by short summaries and `artifact://` URIs
4. final answer -> Markdown generated from the prompt above

This prompt should run after execution and validation evidence are available. It should not be used as a substitute for validation.

