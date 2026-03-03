# Skills and Tools: Abstractions and MCP Interop

Status: Draft
Objective: Define an abstraction where skills orchestrate multi-step procedures and tools are atomic capabilities, with MCP as the preferred tool interface.

## Diagram (Stack — ASCII)

```
Skills Layer:    [Skill: refactor-module]  [Skill: analyze-metrics]
MCP Layer:       [Playwright]  [Postgres]  [GitHub]

Bindings:
- Skill: refactor-module -> Postgres, GitHub
- Skill: analyze-metrics -> Playwright

Actors:
- Operator -> Skill: refactor-module
- Reviewer -> Skill: analyze-metrics

Registry <-> Evaluation (metadata)
```

## Definitions

- Tool: Atomic, side-effectful/external capability with a typed IO schema (e.g., `search`, `db.query`, `browser.click`).
- Skill: LLM-controlled procedure that may invoke one or more tools and produce an artifact (e.g., “refactor module”, “triage bug”, “write ADR”).

## Design Principles

- MCP-first tools: Prefer MCP servers for tool connectivity; fall back to native adapters when MCP is unavailable.
- Typed contracts: Pydantic (or equivalent) schemas for inputs/outputs; strict error boundaries.
- Safety and governance: timeouts, quotas, side-effect levels (read/write/network), allow/deny lists.
- Discoverability: registries for tools and skills with metadata (capability, latency, auth).

## Proposed Interfaces (illustrative)

```python
# Tool
class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    side_effect: Literal["none", "read", "write", "network"]

class ToolClient(Protocol):
    def call(self, name: str, payload: Dict[str, Any], timeout_s: int = 30) -> Dict[str, Any]:
        ...

# Skill
class SkillSpec(BaseModel):
    name: str
    description: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    required_tools: List[str]

class Skill(Protocol):
    def run(self, inputs: Dict[str, Any], tool_client: ToolClient, ctx: Dict[str, Any]) -> Dict[str, Any]:
        ...
```

## MCP Interoperability

- MCP adapter implements `ToolClient`, binding to MCP servers (GitHub, Playwright, Postgres, HTTP/Fetch, Filesystem, Web search/scrape).
- Skills declare tools by name; the registry resolves MCP endpoints and enforces governance.
- Logging: every tool call carries metadata (server, method, latency, result size) to feed LangFuse.

## Registry Responsibilities

- Catalog capabilities and health; surface auth requirements and quotas.
- Contract tests for critical tools; mock modes for eval.
- Versioning: skills pin tool versions or capability tags.

## ADK Integration Notes

- Keep `adk_adapter.py` and `adk_domain_agent.py` stable; expose hook points to dispatch skill/tool calls through the registry.
- Place implementations under `src/aether_frame/framework/tools/` and `src/aether_frame/agents/skills/`.

## References

- [MCP Servers Directory (Official)](https://mcpservers.org/) and [MCP Awesome](https://mcp-awesome.com/) (2025–2026 updates).
- [Claude Code: Best Practices for Agentic Coding](https://www.anthropic.com/engineering/claude-code-best-practices) (Anthropic, 2025-04-18).
- [Claude Skills vs. MCP: A Technical Comparison for AI Workflows](https://intuitionlabs.ai/articles/claude-skills-vs-mcp) (IntuitionLabs, 2025-10).
- [Claude Skills vs MCP vs LLM Tools/Plugins: What to Use When (2025)](https://skywork.ai/blog/ai-agent/claude-skills-vs-mcp-vs-llm-tools-comparison-2025/) (Skywork AI, 2025-10-16).
- [Enhance Claude’s Skills with MCP for Improved Workflows](https://www.gend.co/blog/claude-mcp-skills-enterprise-workflows) (Gend, 2025-12-19).
- [Is MCP Already Outdated? Anthropic Shipped Skills—and How to Pair Them with Milvus](https://milvus.io/blog/is-mcp-already-outdated-the-real-reason-anthropic-shipped-skills-and-how-to-pair-them-with-milvus.md) (Milvus, 2025-11-19).
- [ADK Tools Documentation & Limitations](https://github.com/google/adk-docs/blob/main/docs/tools/limitations.md).

---

## Research Inputs & Rationale

- **MCP directories** show the breadth of servers and highlight the need for a registry with metadata (side-effects, auth). That informs our registry schema.
- **Anthropic & IntuitionLabs content** stresses Skills as procedure packs to cut context bloat, while MCP remains the execution substrate; hence the Skill vs MCP decision matrix.
- **Skywork/Gend/Milvus case studies** demonstrate enterprise workflows combining Skills (SOPs) with MCP tooling to enforce governance and reduce token costs—mirrored here via governance policies and “schemas outside prompt” rule.

---

## Decisions & Trade-offs

- Skills encode SOPs and minimize prompt bloat; MCP provides durable, typed capabilities.
- Prefer MCP-first for portability and governance; allow native shims where MCP servers are unavailable.
- Keep schemas out of prompts; reference by name and minimal metadata to reduce token costs.

## Applicability & Non-Applicability

- Applicable: workflows requiring multiple tools with governance (time/quotas/side-effects), auditability, and repeatability across environments.
- Caution: ultra-low-latency hot paths (consider direct native integration), or tools lacking stable schemas.

## MVP → Enhanced Path

- MVP: Tool registry (capabilities, side-effects, quotas), MCP adapter implementing `ToolClient`, basic Skill spec and execution interface.
- Enhanced: contract tests, health checks, canary modes, versioned skill packs, mock tools for evaluation.

## Decision Matrix (When to use what)

- Use Skill + MCP: default choice; structured SOPs + portable tools.
- Use Skill + Native: when no MCP server exists or when shaving latency is critical.
- Use bare MCP tool: for simple atomic operations within an existing Skill.

## Registry Metadata (Example)

```json
{
  "tool": "postgres.query",
  "capability": "sql",
  "side_effect": "read",
  "timeouts_s": 20,
  "rate_limit_rps": 5,
  "auth": "env:PG_...",
  "version": "1.2.0",
  "tags": ["db", "prod-allowed"],
  "allowed_roles": ["operator"],
  "observability": {"trace": true, "payload_mask": ["password"]}
}
```

## Skill Skeleton (Illustrative)

```yaml
name: refactor-module
description: Safely refactor a Python module and run tests
inputs: { module: str, goal: str }
outputs: { diff_path: str, test_report: str }
required_tools: [fs.read, fs.write, bash.run, pytest.run]
steps:
  - plan: analyze module structure and dependencies
  - change: create branch and apply minimal diffs
  - validate: run tests and static checks
  - summarize: produce diff path and report
policy:
  side_effects: ["write"]
  timeouts_s: 300
  acceptance: ["tests pass", "lint ok"]
```

## Governance Policies

- Side-effect levels: none/read/write/network; enforce allow/deny lists.
- Quotas and budgets: time, tokens, calls per task.
- Observability: trace tool calls (server, method, latency, size) and mask sensitive fields.

## ADK Integration Notes (Planning Only)

- Keep façades stable; add hook points to dispatch skill/tool calls through the registry.
- Place runtime-independent specs under `src/aether_frame/framework/tools/` and `src/aether_frame/agents/skills/` (naming only; no code changes in this planning phase).

### Existing Aether Frame Surface Area

- `src/aether_frame/tools/base/tool.py` defines the abstract `Tool` with `initialize/execute/get_schema/validate_parameters`; the Skill/Tool registry should emit adapters compatible with this base to avoid regressions.
- `src/aether_frame/contracts.ToolRequest/ToolResult` already encapsulate payloads; registry clients should produce/consume these dataclasses for ADK `FunctionTool` calls.
- `adk_agent_hooks` capture ADK callback context/observer metadata; tool invocation telemetry should reuse that path for observability (tying into evaluation metrics).
- ADK exposes `FunctionTool`, `AgentTool`, `MCPTool`, and tooling limitations (per `docs/tools/limitations.md`); our registry must respect ADK constraints (e.g., built-in tool sub-agent limitations) when composing Skills.

## Open Questions

- Which MCP servers are P0 candidates (e.g., Playwright, GitHub, Postgres)?
- How strict should write/network permissions be by default?
- What versioning policy do we need for skill packs across environments?

## Task List (Planning Only)

- Define registry schema and governance knobs
- Draft initial Skill pack list and SOPs
- Curate MCP server shortlist and rationale
- Write contract test plan and mock tool approach
