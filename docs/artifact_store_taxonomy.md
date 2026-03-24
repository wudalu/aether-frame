# Artifact Store Taxonomy

Status: Working proposal

Purpose: define what should go into the Artifact Store, what should not, and how to keep the boundary clear relative to the Task Board, session history, traces, and caches.

## 1. Core Rule

The Artifact Store is for immutable, addressable, replayable objects.

Something should go into the Artifact Store when it satisfies one or more of these conditions:

- it must be referenced later through a stable URI
- it is evidence for review, replay, or audit
- it is a step output or final deliverable
- it is too large or too raw to place directly into prompt context
- it needs provenance, hashing, retention, or lineage

Something should not go into the Artifact Store when it is mainly:

- mutable scheduling state
- ephemeral runtime state
- transient chat traffic
- cache material
- secret material

In short:

- `Artifact Store` stores evidence and deliverables
- `Task Board` stores scheduling and coordination state
- `Session / History Store` stores the conversation timeline
- `Trace / Log Store` stores execution telemetry

## 2. What Should Go Into the Artifact Store

| Category | What it contains | Typical examples | Why it belongs |
| --- | --- | --- | --- |
| `source` | external or user-provided inputs | uploaded PDF, source snapshot, retrieved document copy | inputs need provenance and stable references |
| `working` | structured intermediate results used downstream | intent result JSON, slot extraction result, context-pack manifest, tool raw output, checklist result | downstream steps consume them as evidence |
| `step_output` | outputs of one execution step | `report.md`, `table.csv`, `tool_output.json`, `review_checklist.json`, `diff.patch` | they define what one step produced |
| `deliverable` | task-level promoted outputs | PRD, final summary, export package, final report | they are the canonical outputs of the task |
| `evaluation` | artifacts used to score or improve the system | judge result JSON, scorecard snapshot, regression report | they support replay and iteration |

## 3. What Should Not Go Into the Artifact Store

| Category | Typical examples | Where it should live instead |
| --- | --- | --- |
| Live Task Board state | `ready`, `claimed`, `in_progress`, lease IDs, heartbeat, retry counters | Task Board |
| Conversation timeline by default | raw user turns, raw assistant turns, raw streaming deltas | Session or history store |
| Ephemeral runtime state | temporary variables, in-memory plan state, short-lived buffers | runtime memory |
| Cache data | retrieval cache, embedding cache, prompt cache | cache layer |
| Secret material | tokens, credentials, private keys | secret manager |
| Low-value telemetry | debug logs, token-by-token deltas, transport details | trace or log store |

## 4. Special Cases

This is the practical split for the most common borderline cases.

| Item | Store as artifact? | Recommendation |
| --- | --- | --- |
| User documents | Yes | treat them as `source` artifacts |
| Model reply | Not by default | store as artifact only when promoted into a deliverable or reusable evidence object |
| Intent recognition result | Yes | store as a structured `working` artifact when downstream logic consumes it |
| Context pack | Partly | store the manifest by default; store the full payload only when exact replay is required |
| Tool raw output | Yes | raw output goes to Artifact Store; prompt gets summary plus `artifact://` URI |
| Task Board | No | do not treat live scheduling state as an artifact; export snapshots only when audit needs them |
| Step artifacts | Yes | they are the core contents of the Artifact Store |
| Evaluation results | Yes | they belong as `evaluation` artifacts |

## 5. Practical Rule for Model Replies

Use this distinction:

- `conversation response`: a normal chat turn; keep it in session history
- `promoted artifact`: a response that becomes a named output, evidence object, or downstream input; write it to the Artifact Store

Examples:

- "Here is a quick answer" -> session history, not artifact
- "Here is the final PRD draft" -> deliverable artifact
- "Here is the intent JSON used by downstream routing/context" -> working artifact

## 6. Minimal Metadata for Every Artifact

At minimum, each artifact should carry:

- `artifact_id`
- `task_id`
- `step_id` if step-scoped
- `kind`
- `content_type`
- `uri`
- `sha256`
- `producer`
- `parents[]`
- `created_at`
- `retention_class`

Optional but useful:

- `schema_version`
- `pii_level`
- `tags`
- `summary`

## 7. MVP Recommendation

For the first implementation, five artifact kinds are enough:

1. `source`
2. `working`
3. `step_output`
4. `deliverable`
5. `evaluation`

That is enough if we keep one boundary clear:

- keep live Task Board state out of the Artifact Store
- keep ordinary chat history out of the Artifact Store unless promoted

## 8. Bottom Line

Your original list is close, but it needs two corrections:

1. `Task Board` itself should not be stored as an artifact type
2. `context-pack manifest` and `evaluation outputs` should be first-class artifact categories

The Artifact Store should hold the things that the system may need to cite, verify, replay, compare, or reuse later.
