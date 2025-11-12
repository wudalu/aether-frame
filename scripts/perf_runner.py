#!/usr/bin/env python3
"""
Aether Frame performance harness.

This script drives synthetic workloads through the Aether Frame AI Assistant so we can
measure latency, throughput, and error envelopes before running full load tests.

Usage examples:
    python scripts/perf_runner.py --scenario latency_smoke
    python scripts/perf_runner.py --scenario burst_load --iterations 50 --concurrency 10
    python scripts/perf_runner.py --dry-run --scenario tool_regression
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from aether_frame.bootstrap import create_system_components
from aether_frame.config.settings import Settings
from aether_frame.contracts import (
    AgentConfig,
    KnowledgeSource,
    TaskRequest,
    UniversalMessage,
)
from aether_frame.contracts.enums import TaskStatus
from aether_frame.execution.ai_assistant import AIAssistant
from aether_frame.execution.task_factory import TaskRequestBuilder
from aether_frame.agents.manager import AgentManager


logger = logging.getLogger("perf_runner")


def _json_default(obj: Any) -> Any:
    """Handle enums and dataclasses when dumping JSON."""
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


@dataclass
class ScenarioSpec:
    """Declarative scenario definition."""

    name: str
    description: str
    iterations: int
    concurrency: int
    prompt: str
    tool_names: List[str] = field(default_factory=list)
    max_expected_latency: float = 5.0  # seconds
    session_mode: str = "per_request"  # per_request | reuse_single | fixed_per_iteration
    agent_mode: str = "per_request"  # per_request | reuse_single
    cleanup_agent: bool = False
    metadata_overrides: Dict[str, Any] = field(default_factory=dict)
    knowledge_sources: List[Dict[str, Any]] = field(default_factory=list)
    message_template: Optional[List[Dict[str, Any]]] = None


DEFAULT_SCENARIOS: Dict[str, ScenarioSpec] = {
    "latency_smoke": ScenarioSpec(
        name="latency_smoke",
        description="Serial baseline to capture cold start + steady-state latency.",
        iterations=5,
        concurrency=1,
        prompt="Return a two sentence summary of the latest system readiness state.",
        max_expected_latency=3.0,
    ),
    "burst_load": ScenarioSpec(
        name="burst_load",
        description="Medium prompt fan-out to measure throughput and queueing.",
        iterations=25,
        concurrency=5,
        prompt=(
            "You are a response summarizer. Given the task metadata JSON below, produce a one paragraph "
            "status update that highlights risks and blockers. Respond with <summary>text</summary>."
        ),
        max_expected_latency=6.0,
    ),
    "tool_regression": ScenarioSpec(
        name="tool_regression",
        description="Stresses tool resolution + routing. Provide actual tool names via --tools flag.",
        iterations=10,
        concurrency=3,
        prompt=(
            "Plan how to enrich customer insights by combining CRM data with live search. "
            "Enumerate the steps and cite which tool should run per step."
        ),
        max_expected_latency=8.0,
    ),
    "session_warm_switch": ScenarioSpec(
        name="session_warm_switch",
        description="Measure cold-start session creation vs. warm resume on ADK runners.",
        iterations=6,
        concurrency=1,
        prompt="Respond with a concise update for ticket AF-142 after checking prior notes.",
        max_expected_latency=3.5,
        session_mode="reuse_single",
    ),
    "multi_user_handoff": ScenarioSpec(
        name="multi_user_handoff",
        description="Stress ADK session routing across many short-lived users.",
        iterations=40,
        concurrency=8,
        prompt="Summarize the latest response for my request and suggest next step approval wording.",
        max_expected_latency=6.5,
        session_mode="fixed_per_iteration",
        metadata_overrides={"tenant": "enterprise_pool"},
    ),
    "runner_lifecycle": ScenarioSpec(
        name="runner_lifecycle",
        description="Force agent/runner churn to validate creation and cleanup costs.",
        iterations=12,
        concurrency=2,
        prompt="Kick off a new specialist agent for policy AF-LC and confirm it completed initialization.",
        max_expected_latency=7.0,
        cleanup_agent=True,
    ),
}


@dataclass
class SampleResult:
    """Captures metrics for one invocation."""

    request_id: str
    latency_sec: float
    status: str
    error: Optional[str] = None
    message_chars: int = 0
    session_id: Optional[str] = None
    agent_id: Optional[str] = None


async def build_runtime(settings: Settings) -> Dict[str, Any]:
    """Initialize system components, assistant, and optional task builder."""
    components = await create_system_components(settings)
    assistant = AIAssistant(
        execution_engine=components.execution_engine,
        settings=settings,
    )
    builder = (
        TaskRequestBuilder(components.tool_service)
        if components.tool_service is not None
        else None
    )
    return {
        "assistant": assistant,
        "builder": builder,
        "agent_manager": components.agent_manager,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aether Frame performance harness")
    parser.add_argument(
        "--scenario",
        default="latency_smoke",
        choices=sorted(DEFAULT_SCENARIOS.keys()),
        help="Scenario identifier (see DEFAULT_SCENARIOS).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        help="Override number of total requests to dispatch.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        help="Override the number of in-flight requests.",
    )
    parser.add_argument(
        "--system-prompt",
        default="You are a lightweight diagnostic agent that responds concisely.",
        help="System prompt for the transient agent created per scenario.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model identifier injected into AgentConfig.model_config.",
    )
    parser.add_argument(
        "--tools",
        default="",
        help="Comma separated list of tool names to resolve via ToolService.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Override the user prompt body for this run.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write JSON metrics.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved scenario config without executing any requests.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (DEBUG, INFO, ...).",
    )
    return parser.parse_args()


def resolve_scenario(args: argparse.Namespace) -> ScenarioSpec:
    base = DEFAULT_SCENARIOS[args.scenario]
    iterations = args.iterations or base.iterations
    concurrency = args.concurrency or base.concurrency
    prompt = args.prompt or base.prompt
    tool_names = [name.strip() for name in args.tools.split(",") if name.strip()]
    base_tool_names = list(base.tool_names)
    metadata_overrides = dict(base.metadata_overrides)
    knowledge_sources = [dict(src) for src in base.knowledge_sources]
    message_template = (
        [dict(msg) for msg in base.message_template] if base.message_template else None
    )
    return ScenarioSpec(
        name=base.name,
        description=base.description,
        iterations=iterations,
        concurrency=concurrency,
        prompt=prompt,
        tool_names=tool_names or base_tool_names,
        max_expected_latency=base.max_expected_latency,
        session_mode=base.session_mode,
        agent_mode=base.agent_mode,
        cleanup_agent=base.cleanup_agent,
        metadata_overrides=metadata_overrides,
        knowledge_sources=knowledge_sources,
        message_template=message_template,
    )


def build_agent_config(args: argparse.Namespace) -> AgentConfig:
    """Provide a small-footprint config for temporary benchmarking agents."""
    model_config: Dict[str, Any] = {"temperature": 0.2}
    if args.model:
        model_config["model"] = args.model
    return AgentConfig(
        agent_type="perf_observer",
        system_prompt=args.system_prompt,
        model_config=model_config,
        available_tools=args.tools.split(",") if args.tools else [],
        description="Autogenerated agent for perf harness runs.",
    )


async def create_task_request(
    builder: Optional[TaskRequestBuilder],
    scenario: ScenarioSpec,
    agent_config: AgentConfig,
    iteration: int,
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> TaskRequest:
    """Create a TaskRequest, resolving tools when the ToolService is available."""
    task_id = f"{scenario.name}-{uuid4().hex[:8]}"
    metadata = {"scenario": scenario.name, "iteration": iteration}
    if scenario.metadata_overrides:
        metadata.update(scenario.metadata_overrides)

    if scenario.message_template:
        messages = [
            UniversalMessage(**message_dict) for message_dict in scenario.message_template
        ]
    else:
        messages = [UniversalMessage(role="user", content=scenario.prompt)]

    knowledge_sources = [
        ks if isinstance(ks, KnowledgeSource) else KnowledgeSource(**ks)
        for ks in scenario.knowledge_sources
    ]

    if builder and scenario.tool_names:
        return await builder.create(
            task_id=task_id,
            task_type="chat.completion",
            description=scenario.description,
            tool_names=scenario.tool_names,
            messages=messages,
            available_knowledge=knowledge_sources,
            metadata=metadata,
            agent_config=agent_config,
            session_id=session_id,
            agent_id=agent_id,
        )

    return TaskRequest(
        task_id=task_id,
        task_type="chat.completion",
        description=scenario.description,
        messages=messages,
        available_knowledge=knowledge_sources,
        metadata=metadata,
        agent_config=agent_config,
        session_id=session_id,
        agent_id=agent_id,
    )


async def run_single_request(
    assistant: AIAssistant,
    request: TaskRequest,
) -> SampleResult:
    """Execute a single request and measure latency."""
    start = time.perf_counter()
    try:
        result = await assistant.process_request(request)
        latency = time.perf_counter() - start
        status = result.status.value if isinstance(result.status, TaskStatus) else str(
            result.status
        )
        message_chars = 0
        for message in result.messages:
            if isinstance(message.content, str):
                message_chars += len(message.content or "")
        return SampleResult(
            request_id=request.task_id,
            latency_sec=latency,
            status=status,
            error=result.error_message,
            message_chars=message_chars,
            session_id=result.session_id,
            agent_id=result.agent_id,
        )
    except Exception as exc:  # pragma: no cover - defensive
        latency = time.perf_counter() - start
        logger.exception("Request %s failed: %s", request.task_id, exc)
        return SampleResult(
            request_id=request.task_id,
            latency_sec=latency,
            status="exception",
            error=str(exc),
        )


async def execute_scenario(
    assistant: AIAssistant,
    builder: Optional[TaskRequestBuilder],
    scenario: ScenarioSpec,
    agent_config: AgentConfig,
    agent_manager: Optional[AgentManager] = None,
) -> Dict[str, Any]:
    """Coordinate concurrent execution for a scenario."""
    sem = asyncio.Semaphore(scenario.concurrency)
    samples: List[SampleResult] = []
    shared_session_id: Optional[str] = None
    session_lock = asyncio.Lock()
    shared_agent_id: Optional[str] = None
    agent_lock = asyncio.Lock()

    async def worker(iteration: int) -> None:
        nonlocal shared_session_id
        nonlocal shared_agent_id
        async with sem:
            session_id = None
            if scenario.session_mode == "reuse_single":
                session_id = shared_session_id
            elif scenario.session_mode == "fixed_per_iteration":
                session_id = f"{scenario.name}-session-{iteration}"

            agent_id = None
            if scenario.agent_mode == "reuse_single":
                agent_id = shared_agent_id

            request = await create_task_request(
                builder,
                scenario,
                agent_config,
                iteration,
                session_id=session_id,
                agent_id=agent_id,
            )
            sample = await run_single_request(assistant, request)
            samples.append(sample)

            if (
                scenario.session_mode == "reuse_single"
                and sample.session_id
                and shared_session_id is None
            ):
                async with session_lock:
                    if shared_session_id is None:
                        shared_session_id = sample.session_id

            if (
                scenario.agent_mode == "reuse_single"
                and sample.agent_id
                and shared_agent_id is None
            ):
                async with agent_lock:
                    if shared_agent_id is None:
                        shared_agent_id = sample.agent_id

            if (
                scenario.cleanup_agent
                and agent_manager
                and sample.agent_id
                and scenario.agent_mode != "reuse_single"
            ):
                await agent_manager.cleanup_agent(sample.agent_id)

    tasks = [asyncio.create_task(worker(i)) for i in range(scenario.iterations)]
    start = time.perf_counter()
    await asyncio.gather(*tasks)
    duration = time.perf_counter() - start

    latencies = [sample.latency_sec for sample in samples]
    success_count = sum(1 for sample in samples if sample.status == TaskStatus.SUCCESS.value)
    error_samples = [asdict(sample) for sample in samples if sample.error]

    def percentile(values: List[float], pct: float) -> Optional[float]:
        if not values:
            return None
        sorted_values = sorted(values)
        if len(sorted_values) == 1:
            return sorted_values[0]
        rank = (pct / 100) * (len(sorted_values) - 1)
        lower = int(rank)
        upper = min(lower + 1, len(sorted_values) - 1)
        weight = rank - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    summary = {
        "scenario": asdict(scenario),
        "iterations": scenario.iterations,
        "concurrency": scenario.concurrency,
        "duration_sec": duration,
        "throughput_rps": scenario.iterations / duration if duration else 0.0,
        "latency_avg_sec": statistics.fmean(latencies) if latencies else None,
        "latency_p50_sec": percentile(latencies, 50),
        "latency_p95_sec": percentile(latencies, 95),
        "success_count": success_count,
        "error_count": len(samples) - success_count,
        "errors": error_samples[:5],  # cap for readability
    }

    if summary["latency_p95_sec"] and summary["latency_p95_sec"] > scenario.max_expected_latency:
        summary["alert"] = "p95 latency exceeds expectation"
    elif summary["error_count"]:
        summary["alert"] = "errors detected"

    return summary


async def async_main() -> Dict[str, Any]:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    scenario = resolve_scenario(args)
    agent_config = build_agent_config(args)

    if args.dry_run:
        payload = {
            "scenario": asdict(scenario),
            "agent_config": asdict(agent_config),
        }
        print(json.dumps(payload, indent=2, default=_json_default))
        return payload

    settings = Settings()
    runtime = await build_runtime(settings)
    summary = await execute_scenario(
        assistant=runtime["assistant"],
        builder=runtime["builder"],
        scenario=scenario,
        agent_config=agent_config,
        agent_manager=runtime.get("agent_manager"),
    )

    rendered = json.dumps(summary, indent=2, default=_json_default)
    print(rendered)

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        logger.info("Wrote metrics to %s", args.output)

    return summary


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
