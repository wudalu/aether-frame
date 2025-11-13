# Aether Frame Observability Plan

This document consolidates the previous *observability_enhancement_plan.md* and *docs/observability_plan.md* into a single English reference that describes our current signals, how we generate metrics/logs, and how to extend the pipeline.

## 1. Objectives

- **End-to-end visibility**: capture every ADK execution (batch and live) with consistent context (agent/session/user, request metadata, token usage, duration).
- **Failure diagnosability**: classify errors with `error_stage`, `error_category`, `failure_reason`, and `is_retriable`, and persist last known input/token snapshots.
- **Metrics-readiness**: expose a single integration point that can publish execution counters/histograms to Prometheus or other backends without touching business code.
- **Operational safety**: allow teams to toggle per-execution log volume and select the metrics backend through environment variables.

## 2. Native ADK Signals

| Signal source | Scenarios | Instrumentation plan |
| --- | --- | --- |
| `google.adk.*` loggers | Runner / LLM events (token counts, tool runs) | Bind JSON handlers and surface via unified logging. |
| Hooks (`before_agent`, `after_agent`, etc.) | Capture request/response/tool payloads | `AdkAgentHooks` wraps these callbacks and funnels data into `ExecutionContext`. |
| `usage_metadata` | `run_async`/`run_live` token stats | Normalize into `token_usage` dictionaries and stash in `TaskResult.metadata`. |
| `AdkObserver.start_trace/add_span` | Lightweight trace tree | Persist as JSON; future exporters can ship to SaaS/OTel. |
| Third-party SDKs | AgentOps/LangWatch/LangSmith | Optional, but the unified metadata structure matches their expectations. |

## 3. Logging & Instrumentation Strategy

### 3.1 Execution log toggle

- Every ADK execution creates `logs/execution_<agent>_<execution>.log` containing the full context produced by `ExecutionContext`.
- Set `AETHER_ENABLE_EXECUTION_LOGS=0` (or `false`, `no`) to disable per-execution files while keeping structured `AdkObserver` entries in the main log (e.g., `logs/aether-frame-test.log`).

### 3.2 Mandatory fields

`AdkAgentHooks` and `AdkObserver` guarantee the following keys before emitting any log/metric:

1. `execution_stats`: `started_at`, `finished_at`, `duration_seconds`, `duration_ms`, `status`.
2. `token_usage`: `prompt_tokens`, `completion_tokens`, `total_tokens`.
3. `input_preview`: last 200 characters for each user/system message.
4. `agent_context`: `session_id`, `adk_session_id`, `user_id`, `runner_id`, `execution_id`, `phase`, `request_mode`.
5. `error_classification`: `error_stage`, `error_category`, `failure_reason`, `is_retriable`, `error_type`, `error_message`.
6. `live_stream_additions`: `stream_closed_by_consumer`, `tool_expected`, plan/tool proposal markers.

### 3.3 Example log excerpt

```text
2025-11-12 11:21:17 | INFO | AdkObserver | ADK execution complete
key_data={
  "task_id": "stream_live_a307fca9",
  "agent_id": "domain_agent_stream_agent_create_16e33486",
  "status": "success",
  "execution_time": 678.89,
  "token_usage": {"prompt_tokens":163,"completion_tokens":114,"total_tokens":277},
  "execution_stats": {"started_at":"...","finished_at":"...","duration_seconds":678.89,"duration_ms":678890},
  "input_preview": [{"role": "user", "preview": "Research three recent developments..."}],
  "agent_context": {"session_id":"...","adk_session_id":"...","user_id":"streaming_test_user","execution_id":"stream_exec_688e3a44"},
  "stream_closed_by_consumer": true
}
```

### 3.4 Dashboard & alert ideas

- **Execution health**: Aggregate success rate and `execution_stats.duration_*` by `phase/test_case/model`, chart P50/P95/P99, and overlay `failure_reason` / `error_category` heat maps.
- **Token / cost**: Stack `token_usage.prompt/completion` or convert tokens to USD via each model’s price sheet to compare agents/users.
- **Live completeness**: Track plan/tool proposal markers, `tool_expected`, and `stream_closed_by_consumer` to spot user interruptions or missing plan/tool coverage.
- **Tool usage**: Use `tool_request/tool_result` entries from the ToolService ExecutionContext to compute success rate, latency distribution, and top failing tools.
- **Session funnel**: Link executions with `agent_context.session_id` to build “create → conversation → live” funnels and highlight abnormal sessions.
- **Alerting**: Fire Prometheus/Cloud Monitoring alerts on `adk_execution_total{status="error"}`, high `execution_stats.duration_seconds`, or spikes in `token_usage.total_tokens` to catch stability/cost regressions quickly.

### 3.5 Metric-to-dashboard reference

| Dashboard | Primary metrics | Labels / dimensions | Notes |
| --- | --- | --- | --- |
| Execution health | `execution_stats.duration_seconds`, `execution_stats.duration_ms`, `adk_execution_total` | `phase`, `test_case`, `model`, `agent_id`, `status` | Use histogram/quantile for latency; counters for success/error trends. |
| Token / cost | `token_usage.prompt_tokens`, `token_usage.completion_tokens`, `token_usage.total_tokens` | `agent_id`, `model`, `user_id`, `phase` | Convert to USD with external price table if needed. |
| Failure heat map | `adk_execution_total{status="error"}`, `failure_reason`, `error_category`, `is_retriable` | `agent_id`, `phase`, `model`, `failure_reason`, `error_category` | Combine with log links for investigation workflows. |
| Live completeness | `tool_expected`, plan/tool proposal markers, `stream_closed_by_consumer` | `test_case`, `model`, `agent_id` | Track ratios: plan emitted?, tool proposal seen?, tool result produced?, stream closed by user? |
| Tool usage | ToolService ExecutionContext (`tool_request`, `tool_result`, duration) | `tool_name`, `tool_namespace`, `agent_id`, `status` | Derive success/failure counts, average tool latency, error distribution. |
| Session funnel | Derived counts per phase (create → conversation → live) using `agent_context.session_id` | `session_id`, `user_id`, `agent_id` | Build funnel views or anomaly tables (e.g., sessions failing in conversation stage). |
| Alerting | `adk_execution_total{status="error"}`, `execution_stats.duration_seconds`, `token_usage.total_tokens` | Same as above + environment (`phase`, `cluster`) | Define static/percentile thresholds for latency, error rate, or token spikes. |

## 4. Metrics Pipeline

### 4.1 Generation flow

1. **AdkAgentHooks** records `start_time` and normalized metadata when `before_execution` fires.
2. **AdkObserver.record_execution_*`** merges metadata from hooks/results and calls:
   - structured logger (`aether_frame.infrastructure.adk.observer`);
   - `ExecutionContext` (per-execution log file, optional);
   - `MetricsBackend` (counter/histogram events).
3. **MetricsBackend** exports the event:
   - default `NullMetricsBackend` does nothing;
   - `PrometheusMetricsBackend` exposes counters/histograms via `prometheus_client` HTTP server (default port `9400`).

### 4.2 Metric schema

Current Prometheus implementation emits:

```text
adk_execution_total{agent_id="domain_agent_x",phase="live_execution",test_case="live_streaming",status="start"} 1
adk_execution_total{agent_id="domain_agent_x",phase="live_execution",test_case="live_streaming",status="success"} 1
adk_execution_duration_seconds_bucket{agent_id="domain_agent_x",phase="live_execution",test_case="live_streaming",le="60"} 0
...
```

- Labels: `agent_id`, `phase`, `test_case`, plus `status` for the counter.
- Histograms use buckets `(1, 5, 10, 30, 60, 120, 300, 600, 1200)`.
- Additional metadata (token usage, failure_reason) remains in log files; these can later be transformed into custom metrics if necessary.

### 4.3 Configuring backends

Environment variables (documented in `.env.example`):

| Variable | Default | Description |
| --- | --- | --- |
| `AETHER_ENABLE_EXECUTION_LOGS` | `1` | Toggle per-execution log files. |
| `AETHER_METRICS_BACKEND` | `none` | `none` or `prometheus`. |
| `AETHER_PROMETHEUS_PORT` | `9400` | HTTP port for exporter when backend is `prometheus`. |

To add a new backend:

1. Implement a subclass of `MetricsBackend` (see `src/aether_frame/observability/metrics_backend.py`) that knows how to send events to your system (e.g., Cloud Monitoring, StatsD, OTLP).
2. Register it in `get_metrics_backend()` and use a new environment value (e.g., `AETHER_METRICS_BACKEND=gcm`).
3. The hooking points in `AdkObserver` remain unchanged; only the backend implementation needs to understand how to upsert metrics.

## 5. Implementation checklist

### Phase A – Observer & Logging (High ROI)
1. Capture `start_time` in hooks and write `execution_stats` on completion. **Done.**
2. Ensure live flows (`adk_live_stream`) populate metadata with duration, input preview, token usage. **Done.**
3. Unify observer metadata + ExecutionContext output, with optional execution log toggle. **Done.**
4. Add unit + E2E tests (`tests/unit/test_adk_adapter_live.py`, `tests/manual/test_complete_e2e.py`) to verify fields. **Ongoing; rerun when logic changes.**

### Phase B – Failure logging
1. Define `ErrorCategory` and wire into adapter/agent/tool metadata. **Done.**
2. Ensure `failure_reason` and `is_retriable` appear in all error paths. **Done.**
3. Centralize `hooks.on_error` to log structure context. **Done.**
4. Regression tests covering tool/model/runtime failures. **In progress** (expand as new scenarios arise).

### Optional extensions
- Export `_metrics/_traces` to ELK or SaaS (AgentOps, LangWatch, etc.).
- Add Prometheus alerts (threshold on `adk_execution_total{status="error"}` or histogram quantiles).
- Generate weekly execution summaries from ExecutionContext logs.

## 6. Verification

1. Run `python -m pytest` and `tests/manual/test_complete_e2e.py --tests live_streaming_mode` (inside `.venv`) to ensure fields appear in `logs/execution_*.log` and `logs/aether-frame*.log`.
2. For Prometheus: set `AETHER_METRICS_BACKEND=prometheus`, visit `http://localhost:<port>/metrics`, confirm counters/histograms are emitted when executing a task.
3. Spot-check `logs/execution_*.log` for `execution_stats` and `token_usage`. Live streams should also include `stream_closed_by_consumer`.

## 7. References

- Uptrace. *AI Agent Observability Explained: Key Concepts and Standards*. 2025-04-16.
- Google ADK Docs. *Callbacks: Observe, Customize, and Control Agent Behavior*.
- Google ADK Docs. *Agent Observability with AgentOps*.
