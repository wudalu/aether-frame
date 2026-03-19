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

### 5.1 Traffic Sample Input

Recommended fields:

1. `request_id`
2. `session_id`
3. `user_message`
4. `task_description`, if present
5. `created_at`
6. `locale`, if available
7. `entry_surface`, if available

### 5.2 Execution Outcome Input

Recommended fields:

1. `final_status`
2. `selected_playbook`, if available
3. `selected_skill_family`, if available
4. `selected_tool_family`, if available
5. `clarification_used`
6. `human_escalation`
7. `error_code`, if available

### 5.3 Capability Seed Input

The tool must start from what the system actually supports.

Recommended sources:

1. current playbooks
2. supported skill families
3. supported task types
4. manually curated capability seed list

## 6. Outputs

The tool should emit reviewable artifacts rather than directly mutating runtime code.

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

## 7. Recommended Workflow

The bootstrap flow should be staged.

### 7.1 Export and Sanitize

```text
raw traffic export
  -> PII masking
  -> deduplication
  -> session-level sampling
  -> labeled traffic sample
```

Rules:

1. remove or mask PII before analysis
2. deduplicate near-identical requests
3. sample by session, not only by row count
4. keep separate buckets for success, clarification, fallback, and failure

### 7.2 Capability Mapping

```text
capability seed list
  + labeled traffic sample
  -> seed intent mapping
```

Rules:

1. begin with 3 to 5 supported user goals
2. map traffic to seed intents first
3. treat unsupported but common traffic as evidence for `unknown` or future roadmap, not immediate new production intents

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
traffic input
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

## 9. Execution Modes

The tool should support a few explicit modes.

### 9.1 `report-only`

Use when the team wants to understand traffic before drafting anything.

Outputs:

1. traffic summary
2. capability mapping report
3. confusion pairs

### 9.2 `draft-registry`

Use when the team wants a first-pass static registry proposal.

Outputs:

1. draft intent list
2. draft slot list
3. draft clarification questions
4. generated artifact files

### 9.3 `evaluate-registry`

Use when the team already has a draft registry and wants to test it on held-out traffic.

Outputs:

1. per-intent precision indicators
2. clarification rate
3. fallback rate
4. high-confusion traffic slices

## 10. Review Loop

The output must be human-reviewable.

Recommended review process:

1. product or domain owner reviews candidate intents
2. engineering reviews whether each intent maps to a distinct execution path
3. team rejects intents that only differ in wording
4. required slots are checked against real downstream execution needs
5. clarification questions are edited to be direct and minimal
6. only then is the registry promoted into `src/aether_frame/intent/registry.py`

## 11. Promotion Criteria

An intent should only be promoted when all of these are true:

1. meaningful traffic volume exists
2. the system supports a real downstream execution path for it
3. the intent is distinguishable from nearby intents
4. required slots are clear and stable
5. clarification behavior is acceptable on held-out traffic

## 12. MVP Recommendation

For the first release, keep the tool simple.

Recommended MVP:

1. read sanitized JSONL or CSV exports
2. start from a manually supplied capability seed file
3. produce a draft JSON registry and a Markdown review report
4. support optional offline LLM summarization for candidate analysis
5. do not auto-write runtime Python code directly

This is enough to get a useful first registry without overbuilding the bootstrap system.

## 13. Summary

The recommended design is:

1. a separate offline bootstrap tool
2. driven by real traffic but constrained by supported capabilities
3. producing review artifacts, not production mutations
4. used to draft the initial static intent registry that the runtime system will consume
