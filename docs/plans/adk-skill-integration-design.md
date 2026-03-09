# ADK Skill Integration Design for Aether Frame (V2)

Status: MVP implementation in progress (core path landed)  
Date: 2026-03-06  
Scope: Add first-class `skill` capability on top of Aether Frame's ADK runtime while keeping ADK façade files stable.

## 1. Goals

This design targets:

1. Industry skill architecture (module boundaries and directory layout).
2. ADK native support for skill capability.
3. Skill definition and execution, including nested `mcp/skill` calls.
4. Skill discovery/injection with minimal `system_prompt` impact.
5. A concrete "minimum runnable skill" baseline.

## 2. Input-Driven Design Changes

Updated from stakeholder input:

1. ADK upgrade is acceptable to enable native skills.
2. The first deliverable is a minimum runnable ADK skill pattern.

Design shift:

1. From "compatibility-first (tool wrapper only)" to "ADK native skill-first".
2. MVP executes explicit skills only; no legacy-agent fallback path.

## 3. Version Strategy

## 3.1 Current vs Target

| Item | Current | Target |
| --- | --- | --- |
| `google-adk` in workspace | `1.13.0` | `>=1.25.0` (recommended `1.26.0`) |
| Native ADK Skills | Not available | Available (experimental in docs) |
| Aether integration mode | Tool-only path | Native skill-first (explicit skill injection) |

## 3.2 Recommendation

1. Upgrade to `google-adk>=1.26.0` (latest on PyPI as of 2026-03-06).
2. Use native ADK skill loading (`load_skill_from_dir`) as P1 baseline.
3. Keep existing MCP tool path for atomic tools; no legacy-agent fallback.

## 4. Minimum Runnable ADK Skill (Official Pattern)

## 4.1 Minimum Files

```text
src/aether_frame/skills/
  builtin/
    weather_advice/
      SKILL.md
```

Minimum requirement:

1. Skill directory must contain `SKILL.md`.

Important current ADK limitation:

1. ADK auto-loads `SKILL.md`; nested script directories are not auto-loaded as executable code by default.

## 4.2 Minimal `SKILL.md` Example

```md
---
name: weather-advice
description: Get weather guidance and summarize in short form.
skill_name: weather_advice
display_name: Weather Advice
category: builtin
status: active
---

# Weather Skill

When user asks weather-related questions:
1. Extract city and date.
2. Use available weather/search tools.
3. Return concise recommendation and uncertainty notes.
```

## 4.3 Minimal Python Wiring

```python
import pathlib

from google.adk import Agent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

weather_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent / "skills" / "builtin" / "weather_advice"
)

my_skill_toolset = SkillToolset(skills=[weather_skill])

root_agent = Agent(
    name="assistant",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant.",
    tools=[my_skill_toolset],
)
```

This is the smallest official skill pattern that runs in ADK today.

## 5. Optimized Architecture for Aether Frame

## 5.1 Runtime Model

Use one execution mode in MVP:

1. `adk_native`: ADK `Skill` objects loaded from local paths.
2. Existing MCP tools remain in ToolService as atomic capabilities.

## 5.2 Directory Proposal

```text
src/aether_frame/
  skills/
    builtin/
      summary_rewrite/
        SKILL.md
    mcp/
      github_issue_triage/
        SKILL.md
    computer_use/
      browser_form_fill/
        SKILL.md
    domain/
      compliance_check/
        SKILL.md
    contracts/
      skill_spec.py
      skill_policy.py
      skill_selection.py
    registry/
      skill_registry.py
      local_skill_discovery.py
      skill_catalog.py
    runtime/
      skill_runtime.py
      call_graph_guard.py
      budget_guard.py
    adapters/
      adk/
        native_skill_loader.py
        skill_callback_bridge.py
```

Category meaning (industry-aligned):

1. `builtin`: pure instruction/procedure skills (low side-effect).
2. `mcp`: skills that mainly orchestrate MCP tools.
3. `computer_use`: UI automation skills (high-risk, isolated governance).
4. `domain`: business-domain skills (optional expansion bucket).

## 5.3 Thin Integration Points

1. `bootstrap.py`: initialize `SkillRegistry` and discovery root.
2. `execution/task_factory.py`: add optional `skill_names` in task metadata.
3. `framework/adk/adk_adapter.py`: resolve selected `skill_names` into runtime context.
4. `agents/adk/adk_domain_agent.py`: inject ADK native skills via `SkillToolset` into `tools`.

This keeps façade files as orchestration glue only.

## 5.4 MCP Tool and Skill Coexistence Model

Principle: keep one execution plane for atomic capabilities, and one orchestration plane for procedures.

1. MCP tools remain atomic capabilities in `ToolService` (current path, no behavior break).
2. Skills become orchestration units (SOP/agentic workflow) and call atomic tools.
3. Agent can choose:
   1. Direct MCP tool call for simple tasks.
   2. Skill invocation when a multi-step procedure is needed.

Runtime layering:

```text
Agent (ADK)
  -> tools:
     - MCP tools (existing)
     - SkillToolset (new)
Skill runtime
  -> calls ToolService for MCP/builtin tools
```

Conflict and routing policy:

1. No name collision between tool names and skill names (enforce namespace prefixes).
2. Explicit `skill_names` is the only selection mode in MVP.
3. If skill unavailable, fail fast with validation error.

## 5.5 Migrating Single-Purpose Agents to Skills

Background fit:

1. Existing "agentic skills" were previously implemented as standalone agents.
2. Many are single-purpose and bounded in scope.
3. Converting these into skills is the right direction to reduce orchestration and prompt overhead.

Decision rule: keep only coordination-heavy roles as agents; convert most specialists to skills.

| Existing component shape | Recommended target | Reason |
| --- | --- | --- |
| Single-purpose specialist agent (one domain, short SOP) | Skill | Better reuse, lower context cost, simpler invocation |
| Router/triage/orchestrator agent | Keep as agent | Owns session-level decisions and delegation |
| Human-approval/security gate agent | Keep as agent (or callback policy module) | Centralized governance boundary |
| Long-running autonomous workflow agent | Keep as agent initially | Higher state and lifecycle complexity |

Recommended migration path (low risk):

1. Inventory current specialist agents and map each to `skill_name`.
2. Extract agent SOP into `SKILL.md` (keep input/output contract explicit).
3. Register skill via local discovery; inject with `SkillToolset`.
4. Run A/B verification on same tasks (result quality, latency, tool-call count).
5. Remove old specialist agent only after acceptance criteria pass.

Anti-pattern to avoid:

1. One old agent => one thin skill shell with no contract cleanup.
2. This preserves complexity without gaining skill-level governance or discoverability.

## 6. Nested Skill / MCP / Agentic Skill Handling (Standard Flow)

Use a unified call graph:

1. `skill_call` (native sub-skill).
2. `tool_call` (ToolService or MCP tool).
3. `agent_call` (AgentTool specialist delegation).

Execution flow for "agentic skill includes further MCP usage":

1. Declaration phase:
   1. Skill metadata declares `required_tools` and `required_skills`.
   2. Each required MCP tool carries side-effect level (`read/write/network`).
2. Preflight phase:
   1. Validate tool/skill existence in registry.
   2. Validate user/tenant permissions and auth headers.
   3. Build execution budget (`max_depth`, timeout, tool-call quota).
3. Execution phase:
   1. Enter skill stack frame with `call_id`, `parent_call_id`, `depth`.
   2. Invoke MCP via ToolService (do not bypass existing validation path).
   3. Propagate contextual metadata (`session_id`, `execution_id`, approval context).
4. Governance phase:
   1. Policy inheritance: child cannot escalate parent side-effect ceiling.
   2. Approval inheritance: if parent requires approval, child write/network calls remain approval-gated.
5. Completion phase:
   1. Aggregate outputs into structured `SkillResult`.
   2. Emit tool-by-tool and skill-level telemetry.

Mandatory guardrails:

1. Cycle detection by ancestry path.
2. Max depth (default `3`).
3. Time/token/tool-call budget per top-level skill run.
4. Structured error boundary (no silent fallback).
5. Fail-fast on missing dependencies in P1.

Failure handling recommendation:

1. MCP tool failure inside skill: return typed step error with retryability flag.
2. Nested skill failure: bubble up with `failed_node_id` and partial artifacts.
3. Timeout/budget exhaustion: terminate subtree and return deterministic status (`budget_exceeded`).

## 7. Discovery and Injection with Minimal Prompt Impact

Recommended injection mode:

1. Discover local skills under `src/aether_frame/skills/{builtin,mcp,computer_use,domain}/**/SKILL.md`.
2. Inject selected skills via ADK `SkillToolset` into `tools` (not inlined SOP in system prompt).
3. Keep `system_prompt` stable; add only one invariant sentence if needed.
4. Put large procedural content in skill files/artifacts, not prompt body.
5. Enforce policy and budgets via callbacks/guards.

Prompt impact comparison:

| Strategy | Prompt impact | Recommended |
| --- | --- | --- |
| Inline full skill SOP into system prompt | High | No |
| Native ADK SkillToolset injection | Low | Yes (default) |

## 8. Simplest Frontend Skill Discovery (Approved MVP)

Confirmed direction: explicit skill selection from frontend, no profile abstraction in MVP.

## 8.1 Minimal Data Source

1. Startup scan: `src/aether_frame/skills/{builtin,mcp,computer_use,domain}/**/SKILL.md`.
2. Build in-memory catalog: `skill_name -> metadata + path`.
3. Metadata fields for MVP:
   1. `skill_name`
   2. `display_name`
   3. `short_description`
   4. `display_order` (`int`, default `1000`)
   5. `category` (`builtin/mcp/computer_use/domain`)
   6. `status` (`active` only in MVP)

## 8.2 Minimal API Contract

1. `GET /v1/skills`
   1. Returns active skills in stable order (`category -> display_order -> skill_name`).
   2. Returns `catalog_hash` for frontend/cache consistency checks across instances.
2. `POST /v1/tasks`
   1. Accepts explicit `metadata.skill_names` from frontend.
   2. Runtime validates existence and injects selected skills via `SkillToolset`.

Example `GET /v1/skills` response:

```json
{
  "catalog_hash": "sha256_hex",
  "skills": [
    {
      "skill_name": "summary_rewrite",
      "display_name": "Summary Rewrite",
      "short_description": "Rewrite long text into concise summaries.",
      "display_order": 10,
      "category": "builtin",
      "status": "active"
    }
  ]
}
```

Example payload:

```json
{
  "task_id": "t_001",
  "task_type": "chat",
  "description": "Rewrite this paragraph",
  "metadata": {
    "skill_names": ["summary_rewrite"]
  }
}
```

## 8.3 Runtime Rules

1. Explicit only: if `skill_names` absent, do not auto-select skills.
2. Fail-fast: if any `skill_name` not found or not active, reject request.
3. Deterministic: execution uses exactly provided `skill_names` order.

## 8.4 Out of Scope (Deferred)

1. `profile_id`
2. `POST /v1/skills/resolve`
3. Version pinning (`skill_name@version`)
4. Tenant/role ACL filtering
5. Remote registry and rollout controls

## 9. Delivery Plan (Approved MVP Scope)

Implementation snapshot (current branch):

1. Landed:
   1. `src/aether_frame/skills/` core module (`contracts/registry/runtime/adapters`).
   2. Category skill roots and first builtin sample (`summary_rewrite`).
   3. `bootstrap.py` catalog initialization + adapter injection.
   4. `task_factory.py` skill discovery list + `skill_names` pass-through.
   5. `adk_adapter.py` request-time `skill_names` validation and runtime context wiring.
   6. `adk_domain_agent.py` merged runtime injection (`FunctionTool + SkillToolset`).
   7. Conversion tooling:
      1. `src/aether_frame/skills/runtime/agent_conversion.py`
      2. `scripts/convert_prompt_agents_to_skills.py`
   8. HTTP discovery endpoint:
      1. `GET /v1/skills` via FastAPI app factory (`src/aether_frame/api/http_app.py`)
      2. Returns stable ordered skills with `catalog_hash`
   9. Unit tests for catalog, conversion, ADK tool merging, and HTTP skill discovery.
2. Deferred:
   1. Nested call graph budget/guard modules (`call_graph_guard.py`, `budget_guard.py`).

Phase 0:

1. Upgrade ADK (`>=1.26.0`) and smoke-test existing flows.
2. Create category-based skill root directories (`builtin/mcp/computer_use/domain`).

Phase 1:

1. Add local discovery scanner for `SKILL.md`.
2. Add `GET /v1/skills` minimal catalog endpoint.
3. Add explicit `metadata.skill_names` execution path.
4. Add conversion script: `scripts/convert_prompt_agents_to_skills.py`.
5. Deliver one migrated no-tool skill and verify end-to-end.

Conversion script minimum behavior:

1. Input: exported database agent file path(s) (JSON/JSONL from export script).
2. Filter: convert only no-tool agents (`available_tools == []`).
3. Output: `src/aether_frame/skills/<category>/<skill_name>/SKILL.md`.
4. Modes: `--dry-run` and `--apply`.
5. Report: converted/skipped/failed with reason.

DB export file data contract (for conversion script):

1. Supported formats:
   1. JSON array (`.json`)
   2. JSON Lines (`.jsonl`, one object per line)
2. Required fields per record:
   1. `agent_name` (`string`): source agent unique name
   2. `system_prompt` (`string`): prompt content to migrate into `SKILL.md`
   3. `available_tools` (`array`): must exist; conversion only when empty array
3. Optional fields:
   1. `description` (`string`)
   2. `category_hint` (`string`, one of `builtin|mcp|computer_use|domain`)
   3. `status` (`string`)
   4. `metadata` (`object`)
4. Validation rules:
   1. `agent_name` must be non-empty.
   2. `system_prompt` must be non-empty.
   3. If `available_tools` is non-empty, mark as `skipped_with_tools`.
   4. `skill_name` is derived from `agent_name` (normalize to snake_case and strip `_agent` suffix).
   5. Duplicate derived `skill_name` should be reported as conflict.
5. Minimal JSON example:

```json
[
  {
    "agent_name": "summary_rewrite_agent",
    "system_prompt": "You rewrite long paragraphs into concise summaries.",
    "available_tools": [],
    "description": "Rewrite text with concise style",
    "category_hint": "builtin"
  }
]
```

6. Minimal JSONL example:

```json
{"agent_name":"summary_rewrite_agent","system_prompt":"You rewrite long paragraphs into concise summaries.","available_tools":[],"description":"Rewrite text with concise style","category_hint":"builtin"}
{"agent_name":"issue_triage_agent","system_prompt":"Classify issue severity.","available_tools":["mcp.github.search_issues"],"category_hint":"mcp"}
```

Phase 2:

1. Add call-depth/budget guards for nested skill/MCP calls.
2. Add baseline observability fields (`skill_name`, category, latency).
3. Add conversion report checks in CI for migrated skills.

## 10. Open Decisions

1. Should `skill_names` execution preserve input order strictly (recommended: yes)?
2. Should any existing specialist agent stay as agent in P1?
3. Default policy for network-side-effect MCP calls inside skills (auto-allow vs approval)?

## 11. Cross-References

1. `docs/roadmaps/skills_tools_mcp_abstraction.md`
2. `docs/tool_integration_design.md`
3. `docs/agents.md`

## 12. References (Primary)

1. ADK Skills docs: https://google.github.io/adk-docs/skills/
2. ADK Skills limitations: https://google.github.io/adk-docs/skills/limitations/
3. ADK Function Tools: https://google.github.io/adk-docs/tools-custom/function-tools/
4. ADK MCP Tools: https://google.github.io/adk-docs/tools-custom/mcp-tools/
5. ADK sample (`skills_agent`): https://github.com/google/adk-python/tree/main/contributing/samples/skills_agent
6. ADK `load_skill_from_dir` sample: https://github.com/google/adk-python/blob/main/contributing/samples/skills_agent/skill.py
7. ADK releases: https://github.com/google/adk-python/releases
8. PyPI `google-adk`: https://pypi.org/project/google-adk/
