# Agent Pre‑Launch Capacity Metrics (Top 3)

This checklist focuses on engineering capacity sizing for agent applications when tokens are not the primary bottleneck and streaming is common (HTTP/2 gRPC streams, HTTP chunked, WebSocket/SSE, etc.). It complements docs/b2b_agent_load_profile.md by turning business envelopes into per‑instance resource numbers and instance counts.

Goal: produce actionable pre‑launch numbers using small‑sample measurements (30–60 minutes) and conservative headroom.

References used in this guide (selection):
- Envoy benchmarking guidance (context‑aware benchmarks): https://www.envoyproxy.io/docs/envoy/latest/faq/performance/how_to_benchmark_envoy
- AWS API Gateway WebSocket quotas (idle/connection duration anchors): https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-execution-service-websocket-limits-table.html
- Passenger/Nginx tuning for long‑lived endpoints: https://www.phusionpassenger.com/library/config/nginx/tuning_sse_and_websockets/
- Nginx FD/worker_connections & ulimit background: https://www.robert-michalski.com/blog/nginx-raise-connection-limit
- websockets/Socket.IO memory usage vs connections (near‑linear growth):
  - https://websockets.readthedocs.io/en/stable/topics/memory.html
  - https://socket.io/docs/v4/memory-usage/
- USE Method (Utilization, Saturation, Errors) for capacity/bottleneck analysis: https://www.brendangregg.com/usemethod.html

---

## Metric 1 — Active Stream Concurrency (ASC) and Session Lifecycle

What it is
- ASC is the number of concurrently active sessions (streams) across all transport types (HTTP/2 or gRPC streams, HTTP chunked, WebSocket/SSE). Session lifecycle is the duration each stream keeps resources busy (including tool/RAG waits).

Why it matters
- In streaming systems, “concurrent sessions × duration” drives CPU time, memory working set, and file descriptors far more than request arrival QPS.

How to measure (small sample)
- Log per session: `session_start`, `session_close`, `session_duration` (wall time, include tooling waits), cancellations/timeouts, and arrival rate `session_rate`.
- Compute `session_duration@P50/P95` and `session_rate` during the observation window.

Sizing formulas
- Peak ASC: `ASC_peak ≈ session_rate × session_duration@P95 × spike_factor`.
- Recommended spike_factor: 3.0–3.5 (product launch/end‑of‑quarter spikes). Adjust if you have historical peaks.

Suggested starting anchors (non‑binding)
- Idle timeout: 5–10 minutes (AWS WebSocket idle timeout is 10 minutes; use as an upper bound anchor, not a mandate).
- Max connection duration: keep below a few hours unless there is a hard requirement (AWS anchor: up to 2 hours per connection).
- Timeout/cancel rate: <1–2% in Neutral envelope; investigate tool/RAG tails if higher.

Outputs for sizing
- Use `ASC_peak` as the demand input for per‑instance concurrency calculations (see “Putting it together”).

---

## Metric 2 — CPU per Active Session and Target Utilization

What it is
- CPU time consumed per active session (user+sys) while streaming and orchestrating tools.

Why it matters
- When tokens are not the bottleneck, CPU saturation becomes the primary capacity limiter (serialization, compression, logging, orchestration, retries).

How to measure (small sample)
- From cgroup/container/process stats, compute `CPU_per_session` as “CPU‑seconds per wall‑second” per active session; report `P50/P95`.
- Select a `target_util` per instance (commonly 0.65–0.75) to avoid tail‑latency cliffs.

Sizing formula (CPU bound)
- Per‑instance concurrency (CPU): `concurrent_CPU = cores × target_util / CPU_per_session@P95`.

Suggested starting anchors
- `target_util`: 65–75%.
- Observation window: ≥30 minutes with realistic tool/RAG activity.

---

## Metric 3 — Memory Working Set per Active Session and File Descriptors (FD)

What it is
- Memory: incremental working set per active session (buffers, context, queues), on top of a base resident set size (RSS).
- FD: per session file descriptors (typically 1–2 for a direct connection; 2–4 when proxied), constrained by OS/user `ulimit -n`, proxy `worker_connections`, and `worker_rlimit_nofile`.

Why it matters
- Streaming keeps buffers and context alive; memory grows roughly linearly with concurrent sessions. FD limits cap maximum concurrent connections regardless of CPU.

How to measure (small sample)
- Gather: `base_rss`, `mem_per_session@P50/P95`, `FD_per_session` (include proxy behavior), and `fd_limit` (OS) / `worker_connections` (proxy).

Sizing formulas
- Per‑instance concurrency (Memory): `concurrent_MEM = floor((mem_limit × headroom − base_rss) / mem_per_session@P95)`.
- Per‑instance concurrency (FD): `concurrent_FD  = floor((fd_limit − FD_base) / FD_per_session)`.

Suggested starting anchors
- Memory headroom: ≥20% (to absorb GC spikes, page cache churn, fragmentation).
- FD per session: direct ~1–2; via reverse proxy often ~2+ (upstream+downstream). Validate with `ss -s`/proxy docs.

---

## Putting It Together — From Per‑Instance to Cluster Size

1) Compute per‑instance concurrency under three constraints:
```
concurrent_CPU = cores × target_util / CPU_per_session@P95
concurrent_MEM = floor((mem_limit × headroom − base_rss) / mem_per_session@P95)
concurrent_FD  = floor((fd_limit − FD_base) / FD_per_session)

per_instance_concurrency = min(concurrent_CPU, concurrent_MEM, concurrent_FD)
```

2) Compute peak demand and instance count:
```
ASC_peak = session_rate × session_duration@P95 × spike_factor
instances = ceil(ASC_peak / per_instance_concurrency)
```

3) Envelope linkage (from docs/b2b_agent_load_profile.md)
- Use your Neutral vs. Aggressive business envelopes to set `session_rate` and spike factors. Keep a 15–20% reserve on top of Aggressive for retries/stream overflow.

4) Scaling signals
- HPA triggers: queue_depth, CPU utilization, session_duration@P95.
- Guardrails: FD/ulimit watermarks, OOM early‑warning, timeout/cancel rate.

---

## Example (illustrative only)

Given a service with 4 cores, 6 GiB memory limit, fd_limit=65535, base_rss=600 MiB, FD_base=2, target_util=0.7, headroom=0.2.

Small‑sample (P95):
- session_rate = 8 sessions/s
- session_duration = 45 s
- CPU_per_session = 0.03 CPU‑s/s
- mem_per_session = 3.5 MiB
- FD_per_session = 2
- spike_factor = 3.0

Per‑instance concurrency:
- concurrent_CPU = 4 × 0.7 / 0.03 ≈ 93
- concurrent_MEM = floor(((6144 × 0.2 removed) → 4915 MiB usable) / 3.5) ≈ 1403 (memory not the bottleneck)
- concurrent_FD  = floor((65535 − 2) / 2) ≈ 32766 (FD not the bottleneck)
- per_instance_concurrency = min(93, 1403, 32766) = 93

Peak demand:
- ASC_peak = 8 × 45 × 3.0 = 1080
- instances = ceil(1080 / 93) = 12

---

## Notes & Caveats

- There is no global “canonical” streaming latency/QPS value across stacks; follow the Envoy guidance to benchmark in context (same hardware, same flags, same filters).
- Use idle/connection duration quotas (e.g., AWS) as anchors to set sensible timeouts; do not blindly adopt them as SLOs.
- Memory per connection grows roughly linearly in many stacks, but slopes differ by runtime/implementation (see websockets/Socket.IO docs) — measure your own slope.
- If tokens or model latency later become bottlenecks, extend this checklist with token throughput (TPS), blended cost/1K tokens, and tool/RAG tails as in docs/b2b_agent_load_profile.md.

