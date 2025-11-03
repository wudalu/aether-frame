# ADK Runner / Agent / Session Lifecycle Review

## Background

- The lifecycle design constraints from `docs/session_manager_design.md` (lines 43‑47) describe the original “single active session, destroy-and-recreate, no session reuse” strategy.
- This review inspects `src/aether_frame/framework/adk/adk_adapter.py`, `runner_manager.py`, `adk_session_manager.py`, and the related agent management code to verify how the current implementation aligns with that documentation. The focus is on lifecycle coordination across runners, agents, and sessions.

## Key Findings

1. **Runner cleanup does not sync adapter mappings**  
   `cleanup_runner` (`runner_manager.py:322-360`) tears down the runner but leaves the `agent_id -> runner_id` mapping inside `AdkFrameworkAdapter` (`adk_adapter.py:61-188`). When the user switches back to that agent, `get_runner_for_agent` fails because it references a destroyed runner.

2. **Chat history migration records the wrong `user_id`**  
   `_extract_chat_history` (`adk_session_manager.py:312-328`) reads `runner_context["user_id"]`, but `_create_session_in_runner` (`runner_manager.py:240-269`) overwrites that field on each session creation. With multiple sessions, subsequent history migrations may use an incorrect user ID.

3. **Session reuse path skips existence validation**  
   `coordinate_chat_session` returns the cached `active_adk_session_id` when staying on the same agent (`adk_session_manager.py:76-122`). If an outer layer already cleaned the session (for example via RunnerManager APIs or a background job), the code will hand back an invalid ID and execution will fail.

4. **Reuse strategy lacks updated documentation and guardrails**  
   The implementation now supports controlled reuse (`_select_agent_for_config`, runner reuse, etc.). The design docs still reflect “destroy and recreate”, so we need a written strategy that matches the code: controlled reuse plus proactive cleanup.

5. **Runner / agent / session cleanup entry points are missing**  
   `cleanup_chat_session` (`adk_session_manager.py:265-277`) is never invoked. Proactive cleanup for runners and agents is absent, so long-running workloads may leak resources.

## Current Destruction Mechanics

- **Runner layer**  
  - Capability: `runner_manager.cleanup_runner` and `remove_session_from_runner` free the SessionService and ADK runner.  
  - Trigger: Only invoked indirectly through `AdkSessionManager._cleanup_session_only` (`adk_session_manager.py:224-236`), which itself only runs during agent switching (`_switch_agent_session`). `AdkFrameworkAdapter.shutdown` attempts to call `runner_manager.cleanup_all` (`adk_adapter.py:782-783`), but that method is not implemented.  
  - Gaps: No unified lifecycle entry point (e.g., end-of-session hook or process shutdown). No coordination with `AgentManager`.

- **Session layer**  
  - Capability: `AdkSessionManager.cleanup_chat_session` deletes the session, optionally the runner, and clears the cached `chat_sessions`.  
  - Trigger: The codebase never calls this API; the only destruction path remains `_cleanup_session_only`. Long-running chats or user-initiated “end conversation” actions do not release sessions.  
  - Gaps: Need business- or adapter-level “chat end / timeout” hooks or automatic expiration.

- **Agent layer**  
  - Capability: `AgentManager.cleanup_agent` / `cleanup_expired_agents` remove domain agents and clear internal maps.  
  - Trigger: The ADK adapter never calls these methods. Even after runner/session cleanup, the agent persists in `_agents/_agent_configs`, so reuse logic may select agents with missing runners (related to finding #1).  
  - Gaps: Invoke `AgentManager` when a runner is destroyed or an agent idles too long; keep `_agent_runners` in sync.

> **Recommendation:** Introduce unified cleanup entry points (session end API, adapter-level shutdown hook, scheduled janitor) and ensure RunnerManager, SessionManager, and AgentManager remain consistent.

## Detailed Analysis

### 1. Runner cleanup leaves stale agent mappings
- `_cleanup_session_only` calls `runner_manager.cleanup_runner` when the old session no longer has active sessions (`adk_session_manager.py:224-236`).
- `cleanup_runner` removes internal runner maps but the adapter keeps the old `runner_id` in `_agent_runners`.
- When the user later switches back to the agent, `get_runner_for_agent` (`runner_manager.py:368-394`) sees the stale ID and throws “Runner ... does not exist”.
- **Fix direction:** After `cleanup_runner` succeeds, notify the adapter so it can drop `_agent_runners`, or let the session manager detect the mismatch and rebuild the runner automatically.

### 2. Chat history migration records the wrong user ID
- `_create_session_in_runner` overwrites `runner_context["user_id"]` on every session creation.
- `_extract_chat_history` relies on that field, so for concurrent sessions the most recent user ID “wins”.
- Multi-user scenarios end up mixing histories, leading to privacy and correctness issues.
- **Fix direction:** Store per-session user IDs (e.g., `runner_context["session_user_id_map"]`) or pass the user through explicit parameters. Add regression tests that open concurrent sessions for different users.

### 3. Session reuse path lacks existence checks
- The cached `active_adk_session_id` is trusted blindly.
- If an external cleanup removed that session, the adapter returns an invalid identifier and the downstream call fails.
- **Fix direction:** Validate the session with RunnerManager before returning it. If the session is missing, rebuild; add tests covering forced cleanup while reuse cache is still populated.

### 4. Reuse strategy documentation is outdated
- Current code supports controlled reuse of agents and runners.
- Documentation still promotes “destroy on each run”.
- **Fix direction:** Update the design to describe controlled reuse + proactive cleanup, including session manager state transitions, reuse eligibility checks, and cleanup contracts.

### 5. Cleanup entry points are missing
- `cleanup_chat_session` is never invoked.
- Without explicit hooks, long-running systems accumulate sessions, runners, and agents.
- **Fix direction:**  
  - Add APIs or scheduler hooks to trigger cleanup (e.g., `end_chat_session`, idle timeout).  
  - Wire cleanup callbacks so runner destruction also removes agent mappings and cached sessions.

## Remediation Priorities

| Priority | Item | Actions |
|----------|------|---------|
| **P0** | Fix stale mappings and user ID handling | Address the two highest-impact issues together; add E2E regressions covering switch-back flows and multi-user concurrency; introduce hooks for downstream cleanup. |
| **P1** | Enforce session existence checks and expose cleanup entry points | Validate cached sessions before reuse; add a business-layer API or timeout mechanism to call `cleanup_chat_session`; integrate `AgentManager.cleanup_agent`. |
| **P1/P2** | Align lifecycle strategy | Confirm with product/architecture whether controlled reuse is the target state. If yes, update the design doc, document the session manager state machine, and consider runner pooling or lease-based session management. This work may span multiple iterations. |

> **Execution advice:** Follow the P0 → P1 → P1/P2 sequence, updating design and tests after each phase to keep the lifecycle implementation and documentation aligned.
