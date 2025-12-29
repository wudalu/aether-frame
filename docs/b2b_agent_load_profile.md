# Load Envelope for a 3,000-User B2B Agent App

This note estimates the expected traffic envelope for a seat-based B2B agent application with 3,000 total users. Numbers are grounded in published benchmarks on enterprise AI adoption, knowledge-worker collaboration intensity, and Copilot/RAG workflow complexity.

> Terminology note: “seat” here denotes a licensed enterprise knowledge worker who can invoke the internal productivity agent.

## Industry Inputs
1. **AI adoption baseline.** Microsoft and LinkedIn’s 2024 Work Trend Index surveyed 31,000 people and found that 75% of global knowledge workers already use generative AI at work, 78% bring their own tools, and “power users” save >30 minutes per day.[1]
2. **Workday rhythms.** Microsoft’s 2025 Copilot Usage Report analyzed 37.5 million conversations and shows desktop usage dominated by work/career and technology topics during business hours, with very different evenings/weekend patterns—evidence of pronounced intraday spikes for knowledge tasks.[2]
3. **Adoption intensity and time saved.** The Harvard-led Generative AI Adoption Tracker reports that 37.4% of employed U.S. respondents use genAI for work and already save 1.75% of total work hours through these tools, highlighting the economic pressure for higher seat utilization in focused deployments.[3]
4. **Conversation depth.** Slack data shows the average enterprise user sends 92 messages/day, demonstrating that knowledge workers routinely exchange tens of short turns per shift; dividing those messages across roughly a dozen tasks implies 6–7 conversational turns per task.[4]
5. **LLM workflow complexity.** OpenAI’s 2025 “State of Enterprise AI” report notes that Custom GPTs and Projects now process 20% of enterprise messages and message volume grew 8x year-on-year, meaning a sizable share of user turns invoke multi-step automations beyond a single LLM completion.[5]

## Scenario Options

| Scenario | When to choose | Active seats (peak) | Tasks / user / hr | Messages / task | LLM calls / msg (baseline → peak) | Typical LLM QPS | Peak LLM QPS | Typical message QPS | Peak message QPS | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Conservative | Pilot / opt-in programs with limited AI adoption | 35% (~1,050 users) | 2 | 4 | 1.1 → 1.3 | ~2.6 | ~7.7 | ~2.3 | ~5.8 | Matches Harvard tracker’s current 37% work adoption & 1.75% time savings.[3] |
| Neutral (default) | Organization-wide Copilot deployment | 50% (~1,500 users) | 3 | 5 | 1.2 → 1.5 | ~7.5 | ~28 | ~6.3 | ~19 | Reflects Microsoft Work Trend Index 75% adoption and Copilot daytime usage.[1][2] |
| Aggressive | Power-user teams with agentic automation | 65% (~1,950 users) | 4 | 6 | 1.5 → 1.8 | ~19 | ~80 | ~12.7 | ~44 | Aligns with OpenAI’s 20% automated workflows and Copilot “power user” behavior.[1][2][5] |

### Conservative – Early Rollout / Opt-in Usage
- **When to choose:** Pilot phases or business units where AI usage is limited to enthusiasts. Aligns with the 37% of employees who currently use genAI for work and save ~1.75% of time per the Harvard tracker.[3]
- **Inputs grounded in data:**
  - Active seats during peak hours: 35% (`~1,050` users).
  - Tasks per active user per hour: 2 (occasional Copilot taps for document prep or research).
  - Messages per task: 4 (short request/response loops).
  - LLM/tool calls per message: 1.1 (simple prompts with occasional tool hits).
- **Derived typical load:**
  - Per-user LLM calls/hour: `2 * 4 * 1.1 = 8.8` → `0.0024` QPS.
  - Fleet LLM QPS: `~2.6`.
  - Message ingress QPS: `~2.3`.
- **Peak planning:** assume a `2.5x` concurrency surge (training days, leadership roadshows) and LLM/tool calls rising to `1.3` per message.
  - LLM/RAG peak QPS: `2.6 * 2.5 * (1.3/1.1) ≈ 7.7`.
  - Message peak QPS: `2.3 * 2.5 ≈ 5.8`.

### Neutral – Steady-State Copilot Program (Default)
- **When to choose:** Organization-wide deployment where Copilot is embedded in core workflows and adoption matches Microsoft’s reported 75% usage among knowledge workers.[1]
- **Inputs anchored to Industry Inputs:**
  - Active seats: 50% (`~1,500` concurrent operators) to bridge the 37–75% adoption range in [1][3].
  - Working window: concentrated 8-hour business day per Copilot telemetry in [2].
  - Tasks per active user per hour: 3, reflecting the >30 minutes/day saved by power users and Slack’s 92 messages/day cadence in [4].
  - Messages per task: 5.
  - LLM/tool calls per message: 1.2 baseline; 1.5 when chain-of-thought + tool execution is required.[5]
- **Derived typical load:**
  - Per-user LLM calls/hour: `18` → `0.005` QPS.
  - Fleet LLM QPS: `~7.5`.
  - Message ingress QPS: `~6.3`.
- **Peak planning:** assume `3x` intraday spikes (launch days, quarterly closes) and automation-heavy flows pushing 1.5 calls/message.
  - LLM/RAG peak QPS: `7.5 * 3 * (1.5/1.2) ≈ 28`.
  - Message peak QPS: `6.3 * 3 ≈ 19`.

### Aggressive – Power-User / Agentic Automation
- **When to choose:** Knowledge-intensive teams (engineering, legal, finance) where Copilot, custom GPTs, and Projects are deeply instrumented—matching the 20% automated workflow share and “power user” behavior Microsoft and OpenAI describe.[1][2][5]
- **Inputs:**
  - Active seats: 65% (`~1,950` users) as AI access becomes mandatory for most knowledge roles.
  - Tasks per active user per hour: 4 (multiple micro-workflows chained together).
  - Messages per task: 6 (longer reasoning traces, iterative refinements).
  - LLM/tool calls per message: 1.5 baseline (tool fan-out), rising to 1.8 in peak automation chains.
- **Derived typical load:**
  - Per-user LLM calls/hour: `4 * 6 * 1.5 = 36` → `0.01` QPS.
  - Fleet LLM QPS: `~19`.
  - Message ingress QPS: `~12.7`.
- **Peak planning:** assume `3.5x` spikes (quarter-end close, major release) and LLM/tool calls at 1.8/message.
  - LLM/RAG peak QPS: `19 * 3.5 * (1.8/1.5) ≈ 80`.
  - Message peak QPS: `12.7 * 3.5 ≈ 44`.
- **Guidance:** in this envelope, backends must shard embeddings, pre-warm caches, and use admission control to keep tail latency within SLOs.

## Adoption Ramp & Seat Planning
Active seat share should tie back to the industry benchmarks cited earlier instead of arbitrary linear growth. Use the scenario-driven estimates below as priors and replace them with telemetry once the deployment goes live.

| Scenario | Industry signal | Expected active share of licensed seats | Example concurrency (3,000 seats) |
| --- | --- | --- | --- |
| Conservative | Harvard GenAI Adoption Tracker reports 37.4% of employed U.S. respondents use genAI for work and save ~1.75% time.[3] | **35–40%** | ~1,050–1,200 concurrent seats |
| Neutral | Microsoft + LinkedIn Work Trend Index shows 75% of knowledge workers already use genAI, but live Copilot telemetry indicates daytime concurrency closer to ~50% of licensed seats.[1][2] | **45–55%** | ~1,350–1,650 |
| Aggressive | Copilot “power users” and OpenAI’s enterprise report show 20% of messages already involve automation chains; teams that institutionalize agents tend to drive ≥65% seat concurrency.[1][2][5] | **60–70%** | ~1,800–2,100 |

_How to use:_ multiply the actual seat count at each business milestone (e.g., 3,500 seats after an acquisition) by the active-share band above to size concurrency. Adjust the priors once production telemetry is available.

## Token & Cost Envelope
Assume ~900 prompt tokens + 1,100 completion tokens per LLM call (≈2,000 total). Using Claude Sonnet/Azure GPT-4o reference pricing ($0.002/1K prompt, $0.006/1K completion), each call costs ~$0.016. Include 10% overhead for retries/streaming.

| Scenario | Typical LLM calls/hr (fleet) | Tokens/hr (M) | Tokens/day (M, 8h) | Approx. $/day | Peak tokens/hr (M) | Peak $/day |
| --- | --- | --- | --- | --- | --- | --- |
| Conservative | 8.8 × 1,050 ≈ 9,240 | ~18.5 | ~148 | **$0.016 × 148M / 1K ≈ $890** | ~47 (2.5× surge, 1.3 calls/msg) | **≈ $2.3K** |
| Neutral | 18 × 1,500 = 27,000 | ~54 | ~432 | **≈ $2.6K** | ~162 (3× surge, 1.5 calls/msg) | **≈ $7.8K** |
| Aggressive | 36 × 1,950 = 70,200 | ~140 | ~1,120 | **≈ $6.7K** | ~504 (3.5× surge, 1.8 calls/msg) | **≈ $24K** |

Interpretation: multiply hourly token budgets by business-hour duration, add a 15% reserve for unexpected retries/streaming. Split workloads by region to flatten peaks.

## Reliability Guardrails
Leverage the backend/devops skills to keep capacity within budget:
- **Admission control:** soft-limit per tenant at ~1.2× typical QPS (e.g., 9 QPS for conservative). Hard cap at 1.5× with exponential backoff and actionable error UI.
- **Queue depth SLO:** keep backlog <1 s (conservative) / <2 s (neutral, aggressive). Autoscale on queue depth + P95 latency rather than CPU.
- **Tail latency budgets:** P95 ≤ 6 s (conservative), 8 s (neutral), 10 s (aggressive). If breached twice consecutively, shed load and flush caches.
- **Cache & shard plan:** pre-warm retrieval shards for aggressive cohorts, rotate caches across time zones, isolate tenant embeddings when concurrency >1,500.
- **Traffic shaping:** use weighted-fair queues so aggressive tenants cannot starve conservative pilots; dedicate queue groups per region to absorb timezone spikes.

## Recommended Capacity Option
For planning purposes, treat the **Neutral** scenario as the default envelope while provisioning for the **Aggressive** peak:
- Size core LLM/tooling clusters for the Neutral typical load (≈7.5 LLM QPS, 6.3 message QPS) **plus 30% headroom**, so that organic spikes never leave steady-state performance.
- Pre-provision hot-standby capacity equal to Aggressive peak ÷ 2 (≈40 LLM QPS) that can be brought online within minutes. This ensures you can absorb both bursty adoption and the expansion to 3,500–4,000 seats without re-architecting.
- Keep admission-control thresholds tied to Neutral numbers but allow burst tokens that reach Aggressive levels for specific tenants after automated health checks pass.

This blended approach balances cost (most days run at Neutral) with confidence that the system can scale to Aggressive tiers or seat expansions (e.g., 3,500+ users) without violating SLOs.

Across all tiers, size infrastructure for **≥2x** the modeled peak to absorb retries, streaming tokens, and backlog-drain activities without breaching `P95` SLAs.

## Design and Operations Notes
- Use async queues between the conversation edge and LLM/tool executors to smooth micro-spikes.
- Prefer sticky session caches (recent context window) to cut repeat RAG queries.
- Enforce per-tenant and per-user rate limits slightly above the typical envelope to protect shared backends.
- Autoscale stateless API and worker tiers on queue depth and tail latency, not just CPU.
- Track SLOs on `P95` end-to-end latency and `error/retry` rates; adjust concurrency limits when saturation appears.

## References
[1] Microsoft & LinkedIn, “Microsoft and LinkedIn release the 2024 Work Trend Index on the state of AI at work,” May 8 2024. https://news.microsoft.com/2024/05/08/microsoft-and-linkedin-release-the-2024-work-trend-index-on-the-state-of-ai-at-work/
[2] Microsoft AI, “It’s About Time: The Copilot Usage Report 2025,” Dec 10 2025. https://microsoft.ai/news/its-about-time-the-copilot-usage-report-2025/
[3] Harvard Project on Workforce, “Generative AI Adoption Tracker,” Aug 2025. https://genaiadoptiontracker.com/
[4] SQ Magazine, “Slack Statistics 2025,” noting “The average Slack user sends 92 messages per day.” https://sqmagazine.co.uk/slack-statistics/
[5] SearchYour.AI summary of OpenAI’s “State of Enterprise AI 2025” report; Custom GPTs and Projects process 20% of enterprise messages and total message volume grew 8x year-on-year. https://www.searchyour.ai/en/enterprise-ai-state-2025-openai-report
