# Agents Implementation Notes

## ADK change policy
- `src/aether_frame/agents/adk/adk_domain_agent.py` and `src/aether_frame/framework/adk/adk_adapter.py` are large orchestration files; prefer adding capabilities via dedicated helper modules (for example `src/aether_frame/observability/adk_logging.py`) and keep direct edits to those files minimal.
- When a feature touches multiple layers, add a thin integration call in the existing file and place the core logic in a new module under `src/aether_frame/observability/` or another focused package. This keeps diffs reviewable and simplifies future reuse.
- For observability and logging enhancements, extend the helpers instead of duplicating logic inside the agents. Treat `adk_domain_agent.py`/`adk_adapter.py` as glue only.

## Observability helpers
- `src/aether_frame/observability/adk_logging.py` centralizes ExecutionContext handling, failure metadata derivation, and live-stream logging helpers. Import these utilities instead of re-implementing similar code in agents.
- New telemetry outputs (structured logs, trace exporters, etc.) should extend the helper module or add a sibling module under `observability/`, then expose a single entry point that agents/adapters can call.
