# Intent Registry Bootstrap Design for Aether Frame

Status: Proposed  
Date: 2026-03-19  
Scope: Design an offline, traffic-driven bootstrap tool that analyzes existing user requests and produces draft intent-registry artifacts for the runtime intent-recognition system.

Cross references:
- `docs/intent-recognition_design.md`
- `docs/plans/2026-03-19-intent-recognition-mvp.md`
- `docs/research/2026-03-18-agent-intent-recognition.md`

## 1. Goal

This document defines a separate offline workflow and tool for building the initial static intent registry from existing user traffic.

The tool should help the team:

1. analyze real user requests
2. map those requests onto supported product capabilities
3. discover candidate required slots from successful execution traces
4. draft an initial `IntentSpec` / `SlotSpec` registry
5. generate reviewable artifacts before anything is promoted into production

This tool is not part of the runtime intent-recognition path.

## 2. Why This Should Be Separate

This capability should not live inside the runtime intent layer.

Reasons:

1. it is offline analysis, not request-time execution
2. it may need heavy batch processing, sampling, deduplication, and clustering
3. it should be able to inspect historical outcomes and traces that are not available at runtime
4. it should produce review artifacts for humans, not runtime decisions
5. it should fail independently without affecting live request handling

Recommended boundary:

```text
production traffic export
  -> offline bootstrap script
      -> reports
      -> draft registry artifacts
      -> evaluation summary
  -> human review
  -> checked-in static registry
  -> runtime intent layer
```

## 3. Non-Goals

This tool should not:

1. auto-publish new production intents with no review
2. replace runtime intent recognition
3. create categories that the product cannot actually execute
4. redesign the context layer
5. train a new model in the MVP

## 4. Core Position

The bootstrap tool should be:

1. capability-constrained
2. traffic-informed
3. human-reviewed

The wrong approach is:

```text
all traffic
  -> unsupervised clustering
  -> clusters become production intents
```

That produces wording clusters, not stable execution categories.

The right approach is:

```text
supported capabilities
  + representative traffic
  + successful execution traces
  -> candidate registry drafts
  -> offline evaluation
  -> human review
  -> production registry
```

## 5. Inputs

The tool needs three classes of input.

The primary bootstrap dataset is not a public dataset.

For this tool, the primary input should be:

1. internal interaction traces
2. internal execution outcomes, if available
3. internal capability seeds

Public datasets can still be useful, but only as auxiliary inputs for benchmarking, schema sanity checks, pre-label experiments, or OOS evaluation.

The input schema should be analysis-driven, but it should be expressed as a stable export contract.

That means:

1. analysis goals decide which fields are worth exporting
2. the bootstrap tool should consume a documented JSONL or CSV schema rather than reading live production systems directly
3. each field in that schema should have a known source in the Aether Frame observability, execution, or request path

### 5.1 Internal Interaction Sample Input

Recommended fields:

1. `sample_id`
2. `conversation_id`
3. `session_id`, if available
4. `invocation_id`, if available
5. `user_message`
6. `llm_input_text` or `input_preview`
7. `llm_output_text`
8. `created_at`
9. `agent_name`, if available
10. `model_name`, if available
11. `locale`, if available
12. `entry_surface`, if available

Recommended source mapping:

| Export field | Primary source in Aether Frame | Notes |
| --- | --- | --- |
| `sample_id` | generated export row id, `task_id`, or log record id | Must be stable inside the offline export even if no task contract exists |
| `conversation_id` | session id, chat session id, or another conversation-grouping identifier | This is the preferred grouping key for turn-level reconstruction |
| `session_id` | callback metadata, runtime metadata, or session logs | Optional if the system only has a higher-level conversation id |
| `invocation_id` | ADK callback metadata | Useful when one user turn produces multiple model invocations |
| `user_message` | extracted user text from captured LLM request payloads or `input_preview` | Required field for intent analysis |
| `llm_input_text` or `input_preview` | captured ADK LLM request payloads or `input_preview` logs | Use a preview field if full payload export is too expensive or too sensitive |
| `llm_output_text` | captured ADK LLM response payloads | Used for clarification detection, downstream outcome hints, and manual review |
| `created_at` | observability record timestamp or execution start timestamp | Use the earliest trustworthy timestamp for the analyzed turn |
| `agent_name` | callback metadata such as `agent_name` | Optional enrichment field |
| `model_name` | request payload metadata, if available | Optional enrichment field |
| `locale` | metadata, if available | Optional in MVP |
| `entry_surface` | metadata, if available | Examples: api, chat, workflow, console |

### 5.2 Execution Outcome Input

Recommended fields:

1. `final_status`
2. `selected_playbook`, if available
3. `selected_skill_family`, if available
4. `selected_tool_family`, if available
5. `clarification_used`
6. `human_escalation`
7. `error_code`, if available

Recommended source mapping:

| Export field | Primary source in Aether Frame | Notes |
| --- | --- | --- |
| `final_status` | execution logs, result records, or terminal trace metadata | Required if available; otherwise leave null in MVP exports |
| `selected_playbook` | execution metadata, if populated | If not currently emitted, leave null in MVP rather than inventing the field |
| `selected_skill_family` | execution metadata, if populated | Optional enrichment field |
| `selected_tool_family` | tool request logs, tool trace summaries, or result metadata | Optional enrichment field |
| `clarification_used` | partial-result metadata, clarification markers, or output-text heuristics | This may initially need to be derived rather than directly exported |
| `human_escalation` | approval or handoff metadata, if present | Optional enrichment field |
| `error_code` | error metadata in execution logs or result metadata | Use whatever stable failure code or category is already available |

### 5.3 Capability Seed Input

The tool must start from what the system actually supports.

Recommended sources:

1. current playbooks
2. supported skill families
3. supported task types
4. manually curated capability seed list

Recommended source mapping:

| Seed source | Where to get it | Recommendation |
| --- | --- | --- |
| playbooks | repository definitions, docs, or configuration | Good source if playbook boundaries already match user-facing goals |
| supported skill families | checked-in runtime configuration or docs | Useful when skills are the true execution boundary |
| supported task types | `TaskRequest.task_type` plus product review | Useful only if task types already reflect user goals rather than internal routing |
| curated capability list | manually maintained seed file checked into the repo | Recommended MVP source of truth |

### 5.4 How to Obtain the Input Data

The bootstrap tool should not scrape live systems directly in the MVP.

The intended starting point is an internal offline export, not an open-source corpus.

For Aether Frame, that export should be trace-first.

Recommended acquisition model:

```text
LLM request/response observability
  + execution metadata
  -> one offline export job
  -> sanitized JSONL or CSV files
  -> bootstrap tool
```

Recommended priority order for obtaining the data:

1. export from LLM request/response observability records
2. enrich with execution metadata and tool traces
3. enrich with request/result records only if those contracts already exist and are easy to access
4. if the export is still incomplete, assemble a temporary denormalized dataset with a small manual review pass

For Aether Frame specifically, the most practical sources are:

1. LLM observability-side data
   - captured ADK LLM request and response payload records from `src/aether_frame/framework/adk/llm_callbacks.py`
   - callback metadata such as `invocation_id`, `agent_name`, `task_id`, `session_id`, `user_id`
   - execution logs carrying `input_preview`, `token_usage`, `execution_stats`, and error metadata
2. execution-side enrichment
   - tool request and tool result traces
   - approval or handoff markers
   - failure metadata and terminal status signals
3. optional request/result-side enrichment
   - `TaskRequest` fields if request contracts are already persisted
   - `TaskResult` fields if result contracts are already persisted

Recommended MVP rule:

1. define one denormalized offline export row per analyzed user turn or conversation slice
2. reconstruct that row from LLM request/response traces first
3. do the joining before the bootstrap tool runs
4. keep the bootstrap tool focused on analysis, not on production data access

Why this is trace-first:

1. the bootstrap tool is trying to build Aether Frame's production intent registry
2. production intents must map to this system's real user inputs and real execution behavior
3. in the current state, LLM input/output observability may exist earlier than stable `TaskRequest` or `TaskResult` persistence
4. captured model request/response traces therefore form a practical primary dataset for the first bootstrap iteration

`TaskRequest` and `TaskResult` should be treated as optional enrichment when they exist, not as mandatory bootstrap inputs.

### 5.5 Recommended Export Contract

For the first version, one denormalized JSONL row per analyzed user turn or conversation slice is the cleanest option.

Recommended minimal export shape:

```json
{
  "sample_id": "sample_123",
  "conversation_id": "conv_456",
  "session_id": "sess_456",
  "invocation_id": "inv_789",
  "user_message": "Please summarize this requirement doc and list risks.",
  "llm_input_text": "System: ... User: Please summarize this requirement doc and list risks.",
  "llm_output_text": "I can summarize it. Please share the document or paste the key sections.",
  "created_at": "2026-03-20T10:15:00Z",
  "agent_name": "domain_agent",
  "model_name": "gpt-5.4-mini",
  "locale": "en-US",
  "entry_surface": "chat",
  "final_status": null,
  "selected_playbook": null,
  "selected_skill_family": null,
  "selected_tool_family": null,
  "clarification_used": true,
  "human_escalation": false,
  "error_code": null
}
```

Recommended export preparation steps:

1. choose the source systems for request-side and result-side fields
2. join them into one offline table or JSONL stream
3. remove or mask PII before writing the bootstrap input
4. preserve nulls for fields not yet available instead of fabricating values
5. version the export schema so the bootstrap script can validate it

## 6. Outputs

The tool should emit reviewable artifacts rather than directly mutating runtime code.

The most important point is this:

the output is not "a trained model".

For the MVP, the primary output is a reviewed draft registry package that humans can inspect, revise, and eventually promote into the runtime source of truth.

In other words, this script primarily generates the data and artifacts used by the runtime intent-recognition layer for routing, slot checking, and clarification policy.

The runtime should not read the raw `draft_registry.json` by default.

Required outputs:

1. traffic summary report
2. candidate intent report
3. slot candidate report
4. draft registry artifact
5. offline evaluation report

Recommended output files:

```text
artifacts/intent_bootstrap/
  traffic_summary.json
  candidate_intents.json
  slot_candidates.json
  draft_registry.json
  evaluation_summary.json
  review_report.md
```

Optional output:

1. generated Python scaffold that can be copied into `src/aether_frame/intent/registry.py`

### 6.1 Primary Deliverables

The bootstrap tool should produce two kinds of output:

1. decision-support artifacts for human review
2. one draft registry artifact that can become the basis of `src/aether_frame/intent/registry.py`

That draft registry is the key runtime-facing output.

It is runtime-facing in content, but not runtime-ready by default.

It is expected to feed:

1. deterministic intent narrowing or rule-based fast paths
2. candidate intent lists and label descriptions for optional LLM judgment
3. required-slot checks
4. clarification question selection
5. fallback and unknown-intent handling policy

Recommended promotion path:

```text
bootstrap outputs
  -> human review
  -> edited draft registry
  -> checked-in static registry
  -> runtime intent layer reads promoted registry
```

Promotion rule:

1. `draft_registry.json` is an offline review artifact
2. the runtime should read only the promoted registry
3. the promoted registry may be a checked-in Python module, a checked-in JSON artifact, or another controlled runtime format

### 6.2 Recommended Output Contracts

The outputs should be explicit and machine-readable where possible.

#### `traffic_summary.json`

Purpose:

1. describe the shape and quality of the analyzed dataset
2. show whether the bootstrap input is representative enough to trust

Recommended fields:

```json
{
  "schema_version": "v1",
  "generated_at": "2026-03-20T12:00:00Z",
  "total_samples": 1200,
  "total_conversations": 430,
  "time_range": {
    "start": "2026-03-01T00:00:00Z",
    "end": "2026-03-19T23:59:59Z"
  },
  "status_breakdown": {
    "success": 700,
    "partial": 210,
    "fallback": 160,
    "error": 130
  },
  "model_breakdown": {
    "gpt-5.4-mini": 900,
    "gpt-5.4": 300
  },
  "notes": []
}
```

#### `candidate_intents.json`

Purpose:

1. capture the bootstrap tool's current hypothesis about useful production intents
2. show evidence before anything is promoted

Recommended fields per candidate:

```json
{
  "schema_version": "v1",
  "candidates": [
    {
      "intent_name": "summarize_requirement",
      "description": "Summarize a requirement document and highlight major points.",
      "sample_count": 148,
      "confidence": "medium",
      "example_messages": [
        "Summarize this PRD for me.",
        "Give me the key points from this requirement."
      ],
      "confusing_neighbors": ["analyze_requirement_risks"],
      "recommended_action": "promote"
    }
  ]
}
```

#### `slot_candidates.json`

Purpose:

1. show which execution-blocking fields appear repeatedly for each candidate intent
2. separate required slots from optional ones before registry drafting

Recommended fields:

```json
{
  "schema_version": "v1",
  "slot_candidates": [
    {
      "intent_name": "summarize_requirement",
      "slot_name": "document_source",
      "required": true,
      "evidence_count": 61,
      "clarification_question": "Which requirement document should I use?",
      "clarification_priority": 10,
      "notes": []
    }
  ]
}
```

#### `draft_registry.json`

Purpose:

1. serve as the main machine-readable draft of the production registry
2. provide the clearest handoff artifact from analysis to human review

Non-goal:

1. it is not the default runtime registry file in the MVP

Recommended fields:

```json
{
  "schema_version": "v1",
  "registry_name": "intent_registry_bootstrap_draft",
  "generated_at": "2026-03-20T12:00:00Z",
  "intents": [
    {
      "name": "summarize_requirement",
      "description": "Summarize a requirement document.",
      "examples": [
        "Summarize this requirement document.",
        "Give me the main points from this PRD."
      ],
      "negative_examples": [
        "List the risks in this requirement."
      ],
      "required_slots": [
        {
          "name": "document_source",
          "required": true,
          "description": "The source document or pasted content to summarize.",
          "clarification_question": "Which requirement document should I use?",
          "clarification_priority": 10
        }
      ],
      "optional_slots": []
    }
  ]
}
```

#### `evaluation_summary.json`

Purpose:

1. show whether the draft registry is good enough to review or promote
2. make confusion and fallback behavior visible

Recommended fields:

```json
{
  "schema_version": "v1",
  "evaluated_samples": 300,
  "intent_metrics": [
    {
      "intent_name": "summarize_requirement",
      "estimated_precision": 0.87,
      "clarification_rate": 0.11,
      "fallback_rate": 0.02
    }
  ],
  "top_confusions": [
    {
      "intent_a": "summarize_requirement",
      "intent_b": "analyze_requirement_risks",
      "count": 19
    }
  ]
}
```

#### `review_report.md`

Purpose:

1. give humans a concise narrative summary of what the machine-readable artifacts imply
2. record promotion recommendations and open questions

Recommended sections:

1. dataset coverage
2. proposed intent set
3. rejected or merged candidates
4. required-slot observations
5. clarification recommendations
6. promotion blockers

### 6.3 Optional Intermediate Outputs

These are useful, but not required for the first MVP of the bootstrap tool:

1. pre-labeled review payloads for `Label Studio` or `Argilla`
2. a reviewed gold evaluation slice
3. benchmark comparison outputs for zero-shot versus `SetFit`
4. generated Python scaffold for `src/aether_frame/intent/registry.py`

Recommended rule:

1. the MVP should guarantee the primary deliverables
2. intermediate outputs should remain optional and additive

## 7. Recommended Workflow

The bootstrap flow should be staged.

### 7.1 Export and Sanitize

```text
raw internal trace export
  -> PII masking
  -> deduplication
  -> conversation-level sampling
  -> labeled internal sample
```

Rules:

1. remove or mask PII before analysis
2. deduplicate near-identical requests
3. sample by session, not only by row count
4. keep separate buckets for success, clarification, fallback, and failure

### 7.2 Capability Mapping

```text
capability seed list
  + labeled internal sample
  -> seed intent mapping
```

Rules:

1. begin with 3 to 5 supported user goals
2. map traffic to seed intents first
3. treat unsupported but common traffic as evidence for `unknown` or future roadmap, not immediate new production intents

#### 7.2.1 How to Produce Seed Intents

Seed intents should be produced top-down from supported product capabilities, then refined bottom-up with internal traces.

Recommended method:

1. inventory the real execution paths the product already supports
   - playbooks
   - tool-enabled flows
   - recurring operator workflows
   - supported task families
2. convert each real execution path into a user-goal statement
   - good: "summarize a requirement"
   - good: "analyze requirement risks"
   - bad: "text understanding"
   - bad: "document workflow"
3. merge execution paths that differ only in wording but not in downstream behavior
4. split execution paths only when downstream context, tools, or success criteria differ materially
5. keep the first seed set intentionally small
   - usually 3 to 5 intents for the MVP
6. map representative internal traces onto that small seed set
7. review the mismatch bucket
   - if many traces do not fit any seed intent, decide whether they belong to `unknown` or whether a new supported intent is actually needed

Recommended intent promotion test:

promote a candidate into a seed intent only when all are true:

1. it maps to a real supported execution path
2. it has meaningful traffic volume
3. it is distinguishable from nearby intents
4. it requires meaningfully different context, tools, or success criteria

Practical MVP rule:

1. do not let clustering invent the first seed intents
2. let clustering and summarization challenge or refine a capability-derived seed set

#### 7.2.2 How Much of This Should Be Code-Generated

This should be semi-automated, not fully manual and not fully automatic.

Recommended split:

1. code generates candidate seed intents, evidence summaries, and mismatch buckets
2. humans decide which candidates become real seed intents

Recommended script responsibilities:

1. load internal traces and capability seeds
2. map obvious samples to the capability-derived seed set
3. cluster or summarize the unmatched and ambiguous samples
4. emit candidate intent suggestions with examples and confusion neighbors
5. write those suggestions into `candidate_intents.json`

Recommended human responsibilities:

1. merge duplicate candidates
2. reject unsupported candidates
3. split over-broad candidates only when execution behavior really differs
4. approve the small seed set used for the next registry draft

### 7.3 Candidate Discovery

```text
seed mapping
  + offline summarization / clustering
  -> candidate edge cases
  -> confusion pairs
  -> candidate split/merge suggestions
```

Use of LLMs is acceptable here for:

1. summarizing clusters
2. proposing candidate names
3. surfacing confusing neighboring requests

But results remain draft-only until reviewed.

### 7.4 Slot Mining

```text
successful execution traces
  -> repeated execution requirements
  -> required slot candidates
  -> optional slot candidates
```

Rules:

1. promote only recurring, execution-blocking fields into required slots
2. keep optional details out of MVP unless they materially change execution
3. derive clarification questions from missing required slots

#### 7.4.1 How to Produce Slots

Slots should not be invented from language patterns alone.

They should be derived from what the execution path actually needed in order to proceed correctly.

Recommended method:

1. group internal traces by reviewed or candidate intent
2. inspect successful traces and clarification-heavy traces for each intent
3. ask, for each candidate field:
   - did the agent need this information to continue?
   - did the user have to provide it explicitly?
   - did missing it cause clarification, fallback, or bad execution?
4. promote the field to a required slot only if missing it regularly blocks execution
5. mark it as optional if it improves quality but does not block execution
6. discard it if it is merely decorative, unstable, or too domain-specific for MVP

Recommended slot evidence sources:

1. repeated clarification questions in internal traces
2. repeated tool arguments or downstream action parameters
3. repeated failure or fallback cases caused by missing information
4. repeated user-provided fields in successful executions

Recommended slot tests:

make a field a required slot only when:

1. it is frequently needed
2. it is user-provided rather than always inferable
3. the system should not guess it
4. the execution path behaves materially worse without it

Examples:

1. `document_source`
   - likely required for `summarize_requirement`
2. `risk_focus_area`
   - possibly optional for `analyze_requirement_risks`
3. `output_language`
   - optional unless your execution path truly branches on it

Clarification generation rule:

1. every required slot should have one direct clarification question
2. the question should ask only for the missing execution-blocking information
3. the question should be short enough to fit into the one-turn clarification policy

#### 7.4.2 How Much of This Should Be Code-Generated

Slots should also be produced with code assistance plus human review.

Recommended split:

1. code mines recurring candidate fields and supporting evidence
2. humans decide whether the field is required, optional, or not worth modeling

Recommended script responsibilities:

1. scan reviewed traces per intent
2. extract recurring missing-information patterns
3. inspect repeated tool arguments or downstream parameters, if available
4. detect fields that correlate with clarification or fallback
5. draft clarification questions and priorities
6. write those suggestions into `slot_candidates.json`

Recommended human responsibilities:

1. confirm that a proposed slot is really execution-blocking
2. downgrade weak candidates to optional or remove them entirely
3. edit clarification wording so it is direct and business-appropriate
4. approve the final slot set before registry promotion

### 7.5 Draft Registry Generation

```text
candidate intents
  + slot candidates
  + examples
  -> draft IntentSpec / SlotSpec registry
```

Each draft intent should include:

1. name
2. description
3. positive examples
4. confusing negative examples
5. required slots
6. optional slots
7. clarification questions for required slots
8. clarification priorities

### 7.6 Offline Evaluation

```text
draft registry
  + holdout traffic
  -> intent quality metrics
  -> clarification rate
  -> fallback rate
  -> confusion analysis
```

The registry should not be promoted unless it performs adequately on held-out traffic.

## 8. Script Architecture

Recommended tool shape:

```text
internal trace input
  -> loader
  -> sanitizer
  -> sampler
  -> capability mapper
  -> candidate analyzer
  -> slot miner
  -> registry drafter
  -> evaluator
  -> artifact writer
```

Recommended internal modules:

```text
src/aether_frame/intent/bootstrap/
  __init__.py
  contracts.py
  loader.py
  sanitizer.py
  sampler.py
  capability_mapper.py
  candidate_analyzer.py
  slot_miner.py
  draft_registry.py
  evaluator.py
  writer.py
```

Recommended entrypoint:

```text
scripts/bootstrap_intent_registry.py
```

This keeps the tool scriptable while putting reusable logic under `src/`.

### 8.1 Script-Level Input and Output Contract

Yes, `scripts/bootstrap_intent_registry.py` is the intended top-level script.

Its job is to:

1. read offline bootstrap inputs
2. orchestrate the analysis steps
3. write reviewable artifacts into one output directory

Recommended CLI shape:

```text
python scripts/bootstrap_intent_registry.py \
  --mode <report-only|draft-registry|evaluate-registry> \
  --input-traces <path> \
  --capability-seeds <path> \
  --output-dir <path> \
  [--reviewed-labels <path>] \
  [--public-benchmark-config <path>] \
  [--draft-registry <path>] \
  [--enable-helper-labeling] \
  [--enable-llm-summarization]
```

Required inputs by mode:

| Mode | Required inputs | Optional inputs |
| --- | --- | --- |
| `report-only` | `input-traces`, `capability-seeds`, `output-dir` | `public-benchmark-config` |
| `draft-registry` | `input-traces`, `capability-seeds`, `output-dir` | `reviewed-labels`, `public-benchmark-config`, helper-labeling flags |
| `evaluate-registry` | `input-traces`, `draft-registry`, `output-dir` | `reviewed-labels`, `public-benchmark-config` |

Recommended input files:

1. `input-traces`
   - sanitized JSONL or CSV
   - one row per analyzed user turn or conversation slice
2. `capability-seeds`
   - checked-in YAML or JSON file
   - small list of supported capability-derived candidate intents
3. `reviewed-labels`
   - optional reviewed annotation export from `Label Studio`, `Argilla`, or a simple CSV/JSONL review file
4. `public-benchmark-config`
   - optional config that tells the script which public datasets or baseline experiments to run
5. `draft-registry`
   - existing `draft_registry.json`
   - used only for `evaluate-registry`

Recommended output directory contract:

```text
<output-dir>/
  traffic_summary.json
  candidate_intents.json
  slot_candidates.json
  draft_registry.json
  evaluation_summary.json
  review_report.md
  review_payloads/
    label_studio.jsonl
  benchmarks/
    baseline_summary.json
```

Recommended rule:

1. the script should always write into a dedicated output directory
2. the script should not modify runtime registry files directly
3. promotion into `src/aether_frame/intent/registry.py` should remain a separate human-reviewed step

### 8.2 Example `capability-seeds.yaml`

Recommended minimal example:

```yaml
schema_version: v1
capability_seeds:
  - intent_name: summarize_requirement
    description: Summarize a requirement, PRD, or spec into key points.
    downstream_execution: requirement_summary
    enabled: true
    example_messages:
      - Summarize this PRD for me.
      - Give me the main points from this requirement doc.
    initial_slots:
      - name: document_source
        required: true
        description: The document or pasted content to summarize.
      - name: output_language
        required: false
        description: Preferred output language if the user asks for one.

  - intent_name: analyze_requirement_risks
    description: Analyze a requirement and identify major risks or gaps.
    downstream_execution: requirement_risk_analysis
    enabled: true
    example_messages:
      - What are the main risks in this requirement?
      - Review this spec and list the biggest issues.
    initial_slots:
      - name: document_source
        required: true
        description: The requirement content to analyze.
      - name: risk_focus_area
        required: false
        description: Optional focus such as timeline, scope, dependencies, or compliance.

  - intent_name: generate_requirement_questions
    description: Generate open questions, missing assumptions, or clarification points for a requirement.
    downstream_execution: requirement_question_generation
    enabled: true
    example_messages:
      - What questions should I ask about this spec?
      - Generate clarification questions for this requirement.
    initial_slots:
      - name: document_source
        required: true
        description: The requirement content to inspect.
```

Recommended reading rule:

1. `intent_name` is the seed intent candidate label
2. `description` is the label description used by humans and optional helper labeling models
3. `downstream_execution` points to the real supported execution path
4. `example_messages` help with manual review and helper labeling
5. `initial_slots` are only starting hypotheses and still need evidence from internal traces

### 8.3 Minimum Viable Labeling Script

If the team wants the smallest useful first step, narrow the first implementation to a machine-assisted labeling script only.

In that narrower MVP, the script should not try to produce the full registry draft yet.

It should do only four things:

1. read internal traces
2. read `capability-seeds.yaml`
3. generate candidate intent labels for human review
4. write review-ready outputs plus a small summary

Recommended narrowed CLI shape:

```text
python scripts/bootstrap_intent_registry.py \
  --mode prelabel-review \
  --input-traces <path> \
  --capability-seeds <path> \
  --output-dir <path> \
  [--enable-helper-labeling]
```

Recommended minimal behavior:

1. load one internal sample row at a time
2. extract the text to label from `user_message`
3. compare it only against the intent names and descriptions in `capability-seeds`
4. produce:
   - best candidate intent
   - confidence or score
   - top competing intents
   - `unknown` when nothing looks good enough
5. export low-confidence and high-confusion samples into a human-review payload

Recommended minimal outputs:

```text
<output-dir>/
  prelabels.jsonl
  labeling_summary.json
  review_payloads/
    label_studio.jsonl
  unknown_samples.jsonl
```

Recommended file purposes:

1. `prelabels.jsonl`
   - one row per internal sample
   - machine-suggested label plus scores
2. `labeling_summary.json`
   - counts by predicted intent
   - low-confidence count
   - unknown count
   - top confusion pairs
3. `review_payloads/label_studio.jsonl`
   - import-ready payload for human review
4. `unknown_samples.jsonl`
   - samples that did not fit any seed intent confidently

Recommended non-goals for this first script:

1. no slot mining
2. no draft registry generation
3. no automatic clarification question generation
4. no runtime file mutation
5. no model training requirement

How to use this narrowed MVP:

```text
internal traces
  -> prelabel-review script
  -> human review
  -> reviewed_labels export
  -> later registry-drafting step
```

This gives the team a concrete first deliverable:

1. a reviewed intent-labeled internal dataset
2. evidence for refining seed intents
3. a clean starting point for the later `draft-registry` step

Runnable example files and commands are provided in `docs/examples/intent-bootstrap/`.

### 8.4 Schema Definitions for the Minimum Viable Labeling Script

For the narrowed MVP, define the script contracts explicitly.

Recommended rule:

1. use JSONL for row-based inputs and outputs
2. keep required fields minimal
3. preserve optional fields when available

#### 8.4.1 `input-traces.jsonl`

Purpose:

1. provide the raw internal samples to label
2. give enough context for later human review

Minimum-capture rule:

1. for the narrowed MVP, `user_message` is the only required semantic field for machine-assisted intent labeling
2. this is intentional because intent recognition is primarily trying to understand what the user asked for, not what the assistant later answered
3. `llm_output_text` is still useful, but only as optional enrichment for human review, clarification detection, slot mining, and later evaluation
4. the helper labeling model should not depend on `llm_output_text` as a primary feature in the first iteration, otherwise it risks learning from assistant behavior instead of user intent

Required fields:

1. `sample_id`
2. `conversation_id`
3. `user_message`
4. `created_at`

Recommended optional fields:

1. `session_id`
2. `invocation_id`
3. `llm_input_text`
4. `llm_output_text`
5. `agent_name`
6. `model_name`
7. `final_status`
8. `metadata`

Design note:

1. `user_message`-only traces are acceptable for the first `prelabel-review` pass
2. `llm_output_text` becomes much more important in later phases such as slot extraction, clarification-pattern mining, and registry evaluation
3. if the team can capture only one field from existing traffic, capture `user_message` first

Recommended example row:

```json
{
  "sample_id": "sample_001",
  "conversation_id": "conv_123",
  "session_id": "sess_123",
  "invocation_id": "inv_456",
  "user_message": "Can you summarize this PRD for me?",
  "llm_input_text": "System: ... User: Can you summarize this PRD for me?",
  "llm_output_text": "Please share the PRD or paste the content you want summarized.",
  "created_at": "2026-03-20T10:15:00Z",
  "agent_name": "domain_agent",
  "model_name": "gpt-5.4-mini",
  "final_status": "partial",
  "metadata": {
    "entry_surface": "chat"
  }
}
```

#### 8.4.2 `prelabels.jsonl`

Purpose:

1. store one machine-assisted labeling result per sample
2. make review filtering straightforward

Required fields:

1. `sample_id`
2. `conversation_id`
3. `text`
4. `predicted_intent`
5. `confidence`
6. `top_candidates`
7. `needs_review`
8. `review_reason`

Recommended optional fields:

1. `prediction_source`
2. `llm_output_text`
3. `final_status`
4. `metadata`

Recommended example row:

```json
{
  "sample_id": "sample_001",
  "conversation_id": "conv_123",
  "text": "Can you summarize this PRD for me?",
  "predicted_intent": "summarize_requirement",
  "confidence": 0.88,
  "top_candidates": [
    {"intent_name": "summarize_requirement", "score": 0.88},
    {"intent_name": "analyze_requirement_risks", "score": 0.09},
    {"intent_name": "generate_requirement_questions", "score": 0.03}
  ],
  "needs_review": false,
  "review_reason": null,
  "prediction_source": "helper_labeling_model",
  "llm_output_text": "Please share the PRD or paste the content you want summarized.",
  "final_status": "partial",
  "metadata": {
    "agent_name": "domain_agent"
  }
}
```

Recommended meaning:

1. `predicted_intent="unknown"` is valid
2. `needs_review=true` should be set for low-confidence or high-confusion cases
3. `review_reason` should explain why the sample was routed for review

#### 8.4.3 `review_payloads/label_studio.jsonl`

Purpose:

1. provide an annotation-ready export for human review
2. preserve both raw text and machine suggestions

Recommended structure:

1. use one JSON object per review task
2. store human-visible content under `data`
3. keep machine suggestions read-only in the payload

Recommended example row:

```json
{
  "id": "sample_001",
  "data": {
    "sample_id": "sample_001",
    "conversation_id": "conv_123",
    "text": "Can you summarize this PRD for me?",
    "predicted_intent": "summarize_requirement",
    "confidence": 0.88,
    "top_candidates": [
      {"intent_name": "summarize_requirement", "score": 0.88},
      {"intent_name": "analyze_requirement_risks", "score": 0.09}
    ],
    "review_reason": null,
    "llm_output_text": "Please share the PRD or paste the content you want summarized."
  }
}
```

Recommended human annotation target:

1. one single-label intent choice from the seed intent set plus `unknown`

#### 8.4.4 `labeling_summary.json`

Purpose:

1. summarize what the script produced
2. help decide whether the seed set is usable

Recommended example:

```json
{
  "schema_version": "v1",
  "total_samples": 1200,
  "predicted_intent_counts": {
    "summarize_requirement": 430,
    "analyze_requirement_risks": 290,
    "generate_requirement_questions": 180,
    "unknown": 300
  },
  "needs_review_count": 340,
  "unknown_count": 300,
  "top_confusions": [
    {
      "intent_a": "summarize_requirement",
      "intent_b": "analyze_requirement_risks",
      "count": 41
    }
  ]
}
```

#### 8.4.5 `unknown_samples.jsonl`

Purpose:

1. isolate samples that do not fit any current seed intent confidently
2. provide the main evidence bucket for seed-intent refinement

Recommended rule:

1. use the same row shape as `prelabels.jsonl`
2. include only rows where `predicted_intent` is `unknown` or `needs_review` is true because no candidate is strong enough

### 8.5 Python Contract Sketch for the Narrowed MVP

Because the existing repository contracts are dataclass-based, the first implementation should follow the same style.

Recommended location:

```text
src/aether_frame/intent/bootstrap/contracts.py
```

Recommended minimal contract sketch:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InputTraceSample:
    sample_id: str
    conversation_id: str
    user_message: str
    created_at: str
    session_id: Optional[str] = None
    invocation_id: Optional[str] = None
    llm_input_text: Optional[str] = None
    llm_output_text: Optional[str] = None
    agent_name: Optional[str] = None
    model_name: Optional[str] = None
    final_status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateScore:
    intent_name: str
    score: float


@dataclass
class PrelabelRecord:
    sample_id: str
    conversation_id: str
    text: str
    predicted_intent: str
    confidence: float
    top_candidates: List[CandidateScore] = field(default_factory=list)
    needs_review: bool = False
    review_reason: Optional[str] = None
    prediction_source: str = "helper_labeling_model"
    llm_output_text: Optional[str] = None
    final_status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LabelingSummary:
    schema_version: str = "v1"
    total_samples: int = 0
    predicted_intent_counts: Dict[str, int] = field(default_factory=dict)
    needs_review_count: int = 0
    unknown_count: int = 0
    top_confusions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CapabilitySeedSlot:
    name: str
    required: bool = False
    description: str = ""


@dataclass
class CapabilitySeedIntent:
    intent_name: str
    description: str
    downstream_execution: str
    enabled: bool = True
    example_messages: List[str] = field(default_factory=list)
    initial_slots: List[CapabilitySeedSlot] = field(default_factory=list)


@dataclass
class CapabilitySeedFile:
    schema_version: str = "v1"
    capability_seeds: List[CapabilitySeedIntent] = field(default_factory=list)
```

Recommended implementation rule:

1. use these dataclasses as the internal typed representation
2. read and write JSONL or YAML at the script boundary
3. keep validation lightweight in the first version
4. add stricter schema validation only if data quality becomes a real issue

## 9. Open-Source Accelerators and Public Datasets

Open-source components and public datasets can accelerate the bootstrap process, but they should not define the production registry by themselves.

They are secondary inputs, not the primary source of truth for the registry.

Recommended stance:

1. use open-source assets to accelerate analysis, pre-labeling, benchmarking, and offline evaluation
2. do not let public datasets define the production label space
3. do not let a third-party framework dictate the runtime architecture
4. keep the runtime `IntentRecognitionPipeline` independent from whichever offline bootstrap tools were used

The reason is simple: production intents in Aether Frame must map to real supported execution paths, not just to generic semantic categories.

### 9.1 Recommended Open-Source Components

| Component | Best use in this system | Recommendation |
| --- | --- | --- |
| [Hugging Face zero-shot classification](https://huggingface.co/docs/inference-providers/tasks/zero-shot-classification) | Cold-start pre-labeling against a manually defined capability-bounded candidate label set | Recommended for the first bootstrap pass because it requires no task-specific training |
| [SetFit](https://github.com/huggingface/setfit) | Few-shot baseline once the team has a few hundred reviewed examples | Recommended as the first trained baseline because it is lightweight and works well in low-label settings |
| [Rasa DIETClassifier](https://rasa.com/docs/rasa/reference/rasa/nlu/classifiers/diet_classifier/) | Benchmarking against a mature traditional intent-plus-entity stack | Useful as a comparison point, but not recommended as the MVP runtime dependency because it brings in a heavier platform shape |
| [AutoIntent](https://deeppavlov.github.io/AutoIntent/versions/dev/index.html) | AutoML-style offline benchmarking across multiple intent-classification approaches | Useful after the team has an initial reviewed dataset, but not required for the first bootstrap release |
| [TEXTOIR](https://github.com/thuiar/TEXTOIR) | Research-oriented OOS and open-intent evaluation | Useful for later hardening and research, but not a good first production dependency |
| [Label Studio](https://github.com/HumanSignal/label-studio) | Human review and correction of pre-labeled traffic samples | Recommended as the default open-source annotation tool |
| [Argilla](https://github.com/argilla-io/argilla) | Human-in-the-loop dataset review and iteration | Also viable, especially if the team prefers a feedback-dataset workflow |

### 9.2 Recommended Public Datasets

Public datasets are most valuable for benchmarking model families, testing schema assumptions, and exercising OOS behavior before enough internal data exists.

| Dataset | Best use in this system | Recommendation |
| --- | --- | --- |
| [BANKING77](https://huggingface.co/datasets/PolyAI/banking77) | Fine-grained intent distinction benchmark | Good for measuring whether a candidate model family can separate nearby intents |
| [CLINC OOS](https://huggingface.co/datasets/clinc/clinc_oos) | Unknown, fallback, and OOS evaluation | Strongly recommended for designing and testing unknown-intent behavior |
| [MASSIVE](https://huggingface.co/datasets/AmazonScience/massive) | Intent-plus-slot schema reference and multilingual stress testing | Useful as a reference when refining `IntentSpec` and `SlotSpec` shapes |
| [HWU64](https://huggingface.co/datasets/DeepPavlov/hwu64) | General multi-domain intent benchmark | Useful as an additional offline comparison set |
| [SNIPS](https://huggingface.co/datasets/DeepPavlov/snips) | Sanity checks and tutorial-grade benchmarks | Acceptable as a lightweight starter benchmark, but not representative enough for production decisions by itself |

### 9.3 Recommended Stack for Aether Frame

For Aether Frame, the recommended bootstrap stack is:

1. internal traffic exports as the primary bootstrap dataset
2. public datasets for benchmarking and evaluation habits
3. a helper labeling model for initial machine-assisted prelabeling of internal traces
4. `Label Studio` or `Argilla` for human review
5. a capability-constrained checked-in registry as the production source of truth
6. `SetFit` as the first trained baseline after enough reviewed examples exist

This stack is a better fit than adopting a complete external runtime NLU framework because:

1. the runtime architecture already exists and should remain intact
2. the production label space is defined by product capabilities and execution paths
3. the team mainly needs acceleration for offline analysis and data creation, not a replacement for the execution engine
4. public corpora do not reflect Aether Frame's task semantics closely enough to be the main registry source

Recommended non-goal:

1. do not attempt to make an external framework the new runtime owner of intent recognition in the MVP

### 9.4 How to Integrate These Assets into the Bootstrap Flow

The bootstrap workflow can use these components in a controlled way:

```text
internal traces
  + capability-bounded candidate labels
  -> machine-assisted prelabeling
  -> human review
  -> reviewed bootstrap dataset
  -> draft registry + gold evaluation slice
  -> optional SetFit benchmark

public datasets
  -> benchmark and schema sanity checks
  -> optional baseline experiments
  -> optional OOS evaluation
```

Recommended integration points:

1. after capability mapping, run an optional helper labeling step against the seed intent set
2. export high-uncertainty or high-confusion samples into the annotation tool
3. import reviewed labels back into the bootstrap workspace
4. generate both a draft registry and a reviewed evaluation slice
5. only after this, optionally train or benchmark a lightweight model such as `SetFit`

This means the bootstrap tool should treat open-source models and datasets as accelerators, not as authorities.

### 9.5 How Public Datasets Actually Add Value

Public datasets should not be merged blindly into the production bootstrap dataset.

Instead, they should be used in four controlled ways.

In this document, a `helper labeling model` means a model used only to generate candidate labels for human review.

Examples:

1. a zero-shot classifier
2. a small few-shot classifier such as `SetFit`

#### 9.5.1 Model-family selection

Use public datasets to compare baseline approaches before investing in internal labeling.

Examples:

1. run zero-shot classification on a standard benchmark to see whether the chosen label-description style is viable
2. compare zero-shot versus `SetFit` to decide whether a trained few-shot baseline is worth the complexity
3. use a fine-grained benchmark such as `BANKING77` to see whether the model family can separate nearby intents at all

This is useful because it reduces model-selection guesswork without polluting the production label space.

#### 9.5.2 Schema and slot sanity checks

Public datasets can help the team sanity-check the registry shape.

Examples:

1. use `MASSIVE` to inspect common intent-plus-slot patterns
2. use benchmark labels to pressure-test whether the candidate intent descriptions are too broad or too overlapping
3. inspect public dataset examples when drafting positive and negative example style

This should influence schema design, not define the final production intents.

#### 9.5.3 OOS and fallback evaluation

Public datasets are especially useful for unknown-intent evaluation.

Examples:

1. use `CLINC OOS` to exercise unknown, fallback, and ambiguity handling
2. compare how different baseline classifiers behave when the request does not fit a supported intent
3. use confusion-heavy public examples to test clarification thresholds

This is valuable because internal data is often weak on negative coverage early on.

#### 9.5.4 Pre-labeling support for internal data

Public-data-informed models can help pre-label internal traces, but the internal traces remain the authoritative dataset.

Examples:

1. choose a helper labeling model after public benchmarking, then run it on internal traces
2. train a small `SetFit` baseline only after enough internal reviewed labels exist
3. export low-confidence or high-confusion internal samples for human review

The important constraint is:

1. public data may shape the helper model
2. but the reviewed internal examples shape the production registry

Concrete example:

```text
Step 1: decide the internal candidate intents
  - summarize_requirement
  - analyze_requirement_risks
  - generate_requirement_questions

Step 2: use public datasets to choose a helper baseline
  - compare zero-shot and SetFit on public benchmarks
  - decide that a zero-shot classifier is good enough as the first helper labeling model

Step 3: run that helper baseline on internal traces
  - "Summarize this PRD for me." -> summarize_requirement (0.88)
  - "What are the main risks in this requirement?" -> analyze_requirement_risks (0.83)
  - "Can you list open questions for this spec?" -> generate_requirement_questions (0.79)

Step 4: send low-confidence or high-confusion internal samples to human review
  - humans accept, correct, merge, or reject the machine suggestions

Step 5: build runtime-facing artifacts from the reviewed internal samples
  - positive examples per intent
  - confusing negative examples
  - required slots
  - clarification questions
  - draft_registry.json
```

This is the key distinction:

1. public datasets help choose the helper
2. internal reviewed traces define the registry

### 9.6 What Should Enter the Runtime System

The runtime system should consume only promoted registry artifacts derived from internal review.

Public datasets should not enter the runtime system directly as:

1. production intent labels
2. production slot definitions
3. production clarification questions
4. raw example banks read directly by the runtime pipeline

What may indirectly carry over into the runtime system:

1. a better choice of baseline classifier
2. better label descriptions
3. better OOS thresholds
4. better clarification heuristics
5. better regression and evaluation datasets

In short:

1. public datasets improve how the team builds the system
2. internal reviewed artifacts define what the runtime system actually does

### 9.7 Recommended Extensions to the Script Design

The core tool can stay small, but it is reasonable to leave room for optional acceleration helpers.

Optional helper modules:

```text
src/aether_frame/intent/bootstrap/
  prelabel.py
  label_export.py
  label_import.py
  baseline_benchmark.py
```

Optional execution capabilities:

1. `prelabel`:
   - run machine-assisted prelabeling against the current seed intent set
   - a zero-shot classifier is one acceptable implementation of this helper
2. `export-review`:
   - emit annotation-ready payloads for `Label Studio` or `Argilla`
3. `import-review`:
   - merge reviewed labels back into the bootstrap dataset
4. `benchmark-baseline`:
   - compare zero-shot and `SetFit` performance on the reviewed evaluation slice

These should remain optional so the first MVP of the bootstrap tool can still ship without model training.

## 10. Execution Modes

The tool should support a few explicit modes.

### 10.1 `report-only`

Use when the team wants to understand traffic before drafting anything.

Outputs:

1. traffic summary
2. capability mapping report
3. confusion pairs

### 10.2 `draft-registry`

Use when the team wants a first-pass static registry proposal.

Outputs:

1. draft intent list
2. draft slot list
3. draft clarification questions
4. generated artifact files

### 10.3 `evaluate-registry`

Use when the team already has a draft registry and wants to test it on held-out traffic.

Outputs:

1. per-intent precision indicators
2. clarification rate
3. fallback rate
4. high-confusion traffic slices

## 11. Review Loop

The output must be human-reviewable.

Recommended review process:

1. product or domain owner reviews candidate intents
2. engineering reviews whether each intent maps to a distinct execution path
3. team rejects intents that only differ in wording
4. required slots are checked against real downstream execution needs
5. clarification questions are edited to be direct and minimal
6. only then is the registry promoted into `src/aether_frame/intent/registry.py`

## 12. Promotion Criteria

An intent should only be promoted when all of these are true:

1. meaningful traffic volume exists
2. the system supports a real downstream execution path for it
3. the intent is distinguishable from nearby intents
4. required slots are clear and stable
5. clarification behavior is acceptable on held-out traffic

## 13. MVP Recommendation

For the first release, keep the tool simple.

Recommended MVP:

1. read sanitized JSONL or CSV exports
2. start from a manually supplied capability seed file
3. produce a draft JSON registry and a Markdown review report
4. support optional machine-assisted prelabeling for faster review preparation
5. support optional offline LLM summarization for candidate analysis
6. do not auto-write runtime Python code directly

This is enough to get a useful first registry without overbuilding the bootstrap system.

## 14. Summary

The recommended design is:

1. a separate offline bootstrap tool
2. driven by real traffic but constrained by supported capabilities
3. accelerated by open-source classifiers, annotation tools, and public datasets where useful
4. producing review artifacts, not production mutations
5. used to draft the initial static intent registry that the runtime intent-recognition system will consume for routing and clarification
