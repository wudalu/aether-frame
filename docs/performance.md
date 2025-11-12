# Aether Frame Performance Test Plan

## 1. Performance Goals

### 1.1 External and ADK Benchmarks

- **Enterprise-ready responsiveness:** OpenAI’s Agents SDK deployment report highlights 50,000+ customer interactions per day with a 2.3 s average response time, 0.12 % error rate, and 40 % lower serving cost compared to a custom stack. These are realistic enterprise guardrails for conversational agents at scale.[^1]
- **Tool execution scaling:** Google’s ADK team demonstrated that rewriting blocking tools as async functions shrank end-to-end latency for five stock quote lookups from 475 ms to 165 ms (~2.9× faster), showing the ROI of parallel tool orchestration in the agent runtime.[^2]
- **Inference throughput envelope:** Recent vLLM-based research agent benchmarks keep a 131 k context window while batching up to 256 concurrent sequences on a single NVIDIA L40, which is the bar for keeping throughput high on document-heavy agent workloads.[^3]

### 1.2 Target KPIs for Aether Frame

| KPI | External Anchor | Target for next release | Notes |
| --- | --- | --- | --- |
| Turn latency (P50 / P95) | 2.3 s average @50k requests/day[^1] | ≤ 2.5 s P50, ≤ 4.0 s P95 for knowledge-heavy tasks | Requires cold-start masking + tracing to isolate ADK vs. LLM delay |
| Error budget | 0.12 % observed error rate[^1] | ≤ 1 % total failures, ≤ 0.5 % ADK routing errors | Track via perf harness metadata + TaskResult.error |
| Tool fan-out overhead | 2.9× speed-up from async tools[^2] | ≤ 1.5 × slowdown when 5+ tools fire simultaneously | Enforce async-only regression tests before merge |
| Concurrent throughput | 256 concurrent sequences on L40[^3] | ≥ 25 requests/s steady-state on commodity GPU / ≤ 65 % GPU utilization | Use `burst_load` scenario with ≥ 50 iterations |
| Memory growth per hour | TBD internally | ≤ 50 MB/hour drift (from `docs/adk_performance_testing_summary.md`) | Sampled through psutil poller added to perf harness |

Internal gaps such as session lifecycle latency, GIL contention, and GC pauses are documented in `docs/adk_performance_testing_summary.md` and feed directly into the optimization backlog listed below.

## 2. Performance Evaluation Plan

### 2.1 Macro Strategy

1. **Benchmark parity:** Replicate the external KPIs locally to confirm instrumentation accuracy (latency harness + cost attribution).
2. **Scenario coverage:** Exercise ADK runner orchestration, agent lifecycle flows, and tool fan-out through deterministic scenarios.
3. **Continuous profiling:** Capture CPU/GPU/memory/GIL counters alongside every run to correlate regressions with code paths.
4. **Result ingestion:** Persist JSON summaries under `logs/perf/` and surface deltas in dashboards / PR comments.

### 2.2 Capability-Aligned Scenario Catalog

| Capability | Scenario ID | Workload & Harness Parameters | Primary Metrics | Automation Status |
| --- | --- | --- | --- | --- |
| Agent lifecycle management | `runner_lifecycle` (reused for agent+runner) | 12 serial iterations, `python scripts/perf_runner.py --scenario runner_lifecycle` | Agent creation latency, cleanup latency, RSS delta per cycle | Automated via perf harness (`cleanup_agent=True`) |
| Runner lifecycle management | `runner_lifecycle` + ADK runner telemetry | Same run as above, with ADK runner logs enabled | Runner creation time, idle recycle rate, memory footprint | Automated + requires ADK metrics scrape |
| Session lifecycle & CRUD | `session_warm_switch` | 6 serial iterations, `session_mode=reuse_single` | Cold vs warm latency, session creation count, forced expire time | Automated; delete API step tracked manually until CRUD API lands |
| LLM invocation (latency & throughput) | `latency_smoke`, `burst_load` | `python scripts/perf_runner.py --scenario latency_smoke` and `--scenario burst_load --iterations 50 --concurrency 10` | P50/P95 latency, throughput, token cost | Automated |
| Tool invocation & parallelism | `tool_regression` | `python scripts/perf_runner.py --scenario tool_regression --tools "crm_lookup,doc_indexer,aml_checker"` | Tool resolution latency, parallel tool P95, ADK warning count | Automated, requires async tool implementations |
| Stream mode | `stream_probe` (planned) | `python scripts/perf_runner.py --scenario stream_probe --mode streaming` *(to be implemented)* | Chunk spacing, tool approval latency, drop/retry count | Manual until live harness lands |
| Multimodal support | `multimodal_echo` (planned) | Send multi-part messages (text + base64 image) via integration harness | Content conversion latency, ADK part fidelity, response accuracy | Manual today; perf harness has template hook for future |

### 2.3 Scenario Execution Guides

1. **Agent & Runner Lifecycle**
   - Command:  
     ```bash
     python scripts/perf_runner.py --scenario runner_lifecycle --model gemini-1.5-pro
     ```
   - The harness creates a fresh agent per iteration, records `agent_id` in the JSON summary, and invokes `AgentManager.cleanup_agent` after each request so we can track creation/cleanup latency and RSS drift. Instrument ADK runner logs (`RunnerManager._create_new_runner`) to map agent IDs to runner IDs and confirm that idle runners are reclaimed.

2. **Session Lifecycle & CRUD**
   - Command:  
     ```bash
     python scripts/perf_runner.py --scenario session_warm_switch --model gemini-1.5-pro
     ```
   - The first request sets the baseline for cold session creation; iterations 2–6 reuse the same `session_id`. Compare P50/P95 before/after reuse. To exercise deletion, call the forthcoming Session API (or `AdkSessionManager.cleanup_session`) immediately after the harness finishes to confirm that subsequent runs create fresh sessions.

3. **LLM Invocation Hot Path**
   - Baseline latency: `python scripts/perf_runner.py --scenario latency_smoke`.
   - Throughput sweep:  
     ```bash
     python scripts/perf_runner.py --scenario burst_load \
       --iterations 50 --concurrency 10 --model gemini-1.5-flash
     ```
   - Capture model-side metrics (tokens, cost, cache hits) via provider telemetry and align them with harness output.

4. **Tool Invocation Matrix**
   - Command:  
     ```bash
     python scripts/perf_runner.py --scenario tool_regression \
       --tools "crm_lookup,doc_indexer,aml_checker"
     ```
   - Ensure tools are async-capable; compare harness latency against the single-tool baseline to guarantee ≤1.5× overhead when five tools fire. Inspect `ToolResolver` debug logs and ADK tool execution traces for sequential fallbacks.

5. **Multi-User Handoff**
   - Command:  
     ```bash
     python scripts/perf_runner.py --scenario multi_user_handoff --model gemini-1.5-flash
     ```
   - The harness generates deterministic `session_id`s and tags metadata with `tenant=enterprise_pool`. Use these markers to correlate with runner pool dashboards and verify that session reuse stays ≥80%.

6. **Stream Mode (Planned)**
   - Target workflow: leverage `ExecutionEngine.execute_task_live` to open a streaming session, then measure chunk spacing and backpressure. Automation backlog:
     - Extend `perf_runner.py` with `--mode streaming` to invoke `assistant.start_live_session`.
     - Emit streaming metrics (chunk count, tool approvals) to the JSON summary.
   - Until then, teams should run manual smoke tests using the interactive tool debugger (`tests/interactive_tool_debugger.py`) and capture metrics via trace logs.

7. **Multimodal Support (Planned)**
   - Prepare test payloads that embed `UniversalMessage` parts with images/files.
   - Add a new harness scenario (`multimodal_echo`) that feeds mixed content to `AdkDomainAgent` and asserts that the ADK event converter keeps the attachments intact.
   - Manual interim step: use `tests/integration/test_multimodal_tooling.py` (to be authored) to push base64 screenshots through the ADK adapter and monitor conversion latency.

### 2.4 Automation & Harness Enhancements

- `scripts/perf_runner.py` currently supports:
  - `session_mode` (`per_request`, `reuse_single`, `fixed_per_iteration`) to exercise session recycling.
  - `agent_mode` plus `cleanup_agent` so we can model agent/runner churn.
  - Metadata overrides and future-facing `available_knowledge` hooks (disabled by default) for scenario-specific payloads.
  - JSON summaries that include `session_id`/`agent_id`, making it easy to correlate with ADK logs.
  - `--dry-run` and `--output` flags for CI gating and artifact storage.
- Upcoming work:
  - Add `--mode streaming` and `--multimodal-payload` options to cover the remaining capabilities.
  - Persist psutil/GIL/GC counters alongside the existing metrics to close the loop with the optimization levers below.

Example commands:

```bash
# Multi-tenant concurrency
python scripts/perf_runner.py --scenario multi_user_handoff --model gemini-1.5-flash

# Tool parallelism with custom tool list
python scripts/perf_runner.py --scenario tool_regression --tools "crm_lookup,doc_indexer,aml_checker"
```

### 2.5 Quick Command Reference

| Capability | Command |
| --- | --- |
| Agent / Runner lifecycle | `python scripts/perf_runner.py --scenario runner_lifecycle --model gemini-1.5-pro` |
| Session lifecycle (cold vs warm) | `python scripts/perf_runner.py --scenario session_warm_switch --model gemini-1.5-pro` |
| LLM latency baseline | `python scripts/perf_runner.py --scenario latency_smoke --model gemini-1.5-pro` |
| LLM throughput sweep | `python scripts/perf_runner.py --scenario burst_load --iterations 50 --concurrency 10 --model gemini-1.5-flash` |
| Tool parallelism | `python scripts/perf_runner.py --scenario tool_regression --tools "crm_lookup,doc_indexer,aml_checker"` |
| Multi-user handoff | `python scripts/perf_runner.py --scenario multi_user_handoff --model gemini-1.5-flash` |
| Stream mode (manual) | `python -m pytest tests/manual/test_adk_stream_mode_e2e.py::TestAdkStreamMode::test_streaming_flow` *(until perf harness streaming support lands)* |
| Multimodal payload (manual) | `python -m pytest tests/manual/test_complete_e2e.py -k multimodal_image_analysis` *(placeholder until automated scenario is added)* |

### 2.4 Metrics Capture & Storage

- Latency + throughput metrics flow from harness JSON → `logs/perf/`.
- Resource telemetry (CPU, memory, GIL) will be appended via a lightweight psutil sampler (queued follow-up) and correlated by `scenario` + `iteration` metadata already embedded in `TaskRequest`.
- Raw ADK + system logs land under `logs/` (existing convention) and should be rotated after each run.

## 3. Performance Optimization Levers

| Priority | Hotspot | Evidence | Planned action | Expected ROI |
| --- | --- | --- | --- | --- |
| P0 | Session lifecycle + agent creation | Session creation, switch latency, and cleanup still “TBD” in `docs/adk_performance_testing_summary.md` | Instrument `latency_smoke` with `session_id` reuse toggles, cache agent configs, add watchdog for idle runner cleanup | Removes repeated ADK bootstrap cost; targets ≥ 25 % latency reduction |
| P0 | Tool parallelism | Google ADK data shows 2.9× win when tool async is enforced[^2] | Gate merges with `tool_regression` scenario, add lint rule forbidding sync tools in performance-critical namespaces | Keeps multi-tool tasks within 1.5× serial latency budget |
| P1 | GIL & GC pressure | Pending measurements for GIL contention, GC pause, fragmentation in existing summary doc | Extend harness to record `gc.get_stats()` + `faulthandler.dump_traceback_later`; schedule Python-level profiling sweeps weekly | Unlocks higher concurrency targets and reduces tail latency spikes |
| P1 | Streaming workloads | Event streaming KPIs listed as TBD internally | Add streaming scenario once event layer stabilizes; reuse harness to send `ExecutionMode.STREAMING` requests | Ensures upcoming streaming architecture can inherit baseline KPIs |
| P2 | Cost per request | External anchor of 40 % cost reduction[^1] | Integrate token accounting via LLM provider hooks + `perf_runner` metadata | Provides $ cost dashboards for ROI tracking |

## 4. Phased Performance Reporting

| Phase | Timeline | Activities | Deliverables |
| --- | --- | --- | --- |
| Baseline (Week 1) | Before new optimization work | Run `latency_smoke` + `burst_load` twice daily, capture psutil snapshots | `logs/perf/baseline_*.json`, summary slide with KPI deltas vs. targets |
| Optimization Loop 1 (Weeks 2–3) | Focus on session lifecycle + tool parallelism | Pair perf harness runs with profiling traces after each feature branch | Comparison table of P50/P95, issue list with owners, updated backlog |
| Optimization Loop 2 (Weeks 4–5) | GIL/GC instrumentation & streaming preview | Introduce extended scenarios (50+ iterations), collect GC histograms | Report showing GC pause trends, approval to proceed to broader perf sweep |
| Pre-release Gate | Before release branch cut | Full matrix run + regression vs. previous milestone | “Performance readiness” checklist with pass/fail, attach harness JSON |

Each phase ends with a short summary posted to the engineering channel plus the raw artifacts (`logs/perf/`, profiler traces, Grafana snapshots). Regressions discovered downstream must link back to the corresponding harness run to keep provenance clear.

[^1]: *AI Agent Frameworks 2025: Production-Ready Solutions That Actually Work*, Axis Intelligence, 2025.
[^2]: Bo Yang, *2-Minute ADK: Speed Up Your Agent with Parallel Tools*, Google Cloud Community, 2025.
[^3]: Madhur Prashant, *Efficient LLM Agent Serving with vLLM: A Deep Dive into Research Agent Benchmarking*, Medium, 2025.
