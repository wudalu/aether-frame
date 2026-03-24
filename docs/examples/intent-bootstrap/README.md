# Intent Bootstrap Script Examples

This directory contains the smallest runnable example files for the narrowed bootstrap intent-labeling workflow.

For the short operational summary of the full offline workflow, see:

- [docs/intent-registry-bootstrap_sop.md](/Users/wudalu/hsbc_code/aether-frame/docs/intent-registry-bootstrap_sop.md)

The flow is intentionally two-stage:

1. `prelabel-review`
2. `draft-registry`

These examples are meant to show the data shape and the intended operator workflow, not to represent production-scale traffic.

The example `input-traces.example.jsonl` intentionally includes only `user_message` plus minimal metadata.
This reflects the narrow MVP assumption:

1. machine-assisted intent prelabeling should primarily classify the user ask
2. assistant output is optional enrichment, not a required input, for the first pass
3. later stages such as slot mining and evaluation should add `llm_output_text` when that signal is available

## Files

- `input-traces.example.jsonl`
- `capability-seeds.example.json`
- `reviewed-labels.example.jsonl`

## Stage 1: Machine-Assisted Prelabeling

Run:

```bash
uv run python scripts/bootstrap_intent_registry.py \
  --mode prelabel-review \
  --input-traces docs/examples/intent-bootstrap/input-traces.example.jsonl \
  --capability-seeds docs/examples/intent-bootstrap/capability-seeds.example.json \
  --output-dir /tmp/intent-bootstrap-prelabel \
  --enable-helper-labeling
```

Expected outputs:

```text
/tmp/intent-bootstrap-prelabel/
  prelabels.jsonl
  labeling_summary.json
  review_payloads/
    label_studio.jsonl
  unknown_samples.jsonl
```

Use this stage when:

1. the team wants machine-suggested labels for internal samples
2. the team wants to route low-confidence or unknown samples into human review

## Stage 2: Draft Registry Generation

After human review produces a reviewed-label file, run:

```bash
uv run python scripts/bootstrap_intent_registry.py \
  --mode draft-registry \
  --input-traces docs/examples/intent-bootstrap/input-traces.example.jsonl \
  --capability-seeds docs/examples/intent-bootstrap/capability-seeds.example.json \
  --reviewed-labels docs/examples/intent-bootstrap/reviewed-labels.example.jsonl \
  --output-dir /tmp/intent-bootstrap-draft
```

Expected outputs:

```text
/tmp/intent-bootstrap-draft/
  candidate_intents.json
  slot_candidates.json
  draft_registry.json
  review_report.md
```

Use this stage when:

1. the team already has reviewed internal labels
2. the team wants a first machine-generated registry draft for human promotion

## Operator Notes

Recommended workflow:

```text
internal traces
  -> prelabel-review
  -> human review
  -> reviewed labels
  -> draft-registry
  -> human promotion into runtime registry
```

Important boundary:

1. the runtime should not read raw outputs from this example directory
2. the runtime should read only a promoted registry after review
