# -*- coding: utf-8 -*-
"""Metrics backend integrations for ADK observability."""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MetricsBackend:
    """Interface for observability metrics backends."""

    def record_execution_start(self, *, task_id: str, agent_id: str, metadata: Dict[str, Any]) -> None:
        return

    def record_execution_completion(
        self,
        *,
        task_id: str,
        agent_id: Optional[str],
        status: str,
        execution_time: Optional[float],
        metadata: Dict[str, Any],
    ) -> None:
        return

    def record_execution_error(
        self,
        *,
        task_id: str,
        agent_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        return


class NullMetricsBackend(MetricsBackend):
    """No-op backend when metrics export is disabled."""


class PrometheusMetricsBackend(MetricsBackend):
    """Prometheus metrics exporter (HTTP endpoint)."""

    def __init__(self, port: int = 9400):
        try:
            from prometheus_client import Counter, Histogram, start_http_server
        except ImportError as exc:
            raise RuntimeError(
                "prometheus_client is required for Prometheus metrics backend"
            ) from exc

        start_http_server(port)
        logger.info("Prometheus metrics server started on port %s", port)

        label_names = ["agent_id", "phase", "test_case"]
        self._execution_counter = Counter(
            "adk_execution_total",
            "ADK executions by status",
            labelnames=label_names + ["status"],
        )
        self._duration_histogram = Histogram(
            "adk_execution_duration_seconds",
            "Execution duration in seconds",
            labelnames=label_names,
            buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1200),
        )

    @staticmethod
    def _extract_labels(metadata: Dict[str, Any], agent_id: Optional[str]) -> Dict[str, str]:
        return {
            "agent_id": agent_id or metadata.get("agent_id", "unknown"),
            "phase": str(metadata.get("phase", "unknown")),
            "test_case": str(metadata.get("test_case", "unknown")),
        }

    def record_execution_start(self, *, task_id: str, agent_id: str, metadata: Dict[str, Any]) -> None:
        labels = self._extract_labels(metadata, agent_id)
        self._execution_counter.labels(status="start", **labels).inc()

    def record_execution_completion(
        self,
        *,
        task_id: str,
        agent_id: Optional[str],
        status: str,
        execution_time: Optional[float],
        metadata: Dict[str, Any],
    ) -> None:
        labels = self._extract_labels(metadata, agent_id)
        self._execution_counter.labels(status=status or "unknown", **labels).inc()
        if execution_time is not None:
            self._duration_histogram.labels(**labels).observe(execution_time)

    def record_execution_error(
        self,
        *,
        task_id: str,
        agent_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        labels = self._extract_labels(metadata, agent_id)
        self._execution_counter.labels(status="error", **labels).inc()


_METRICS_BACKEND: Optional[MetricsBackend] = None


def get_metrics_backend() -> MetricsBackend:
    """Return global metrics backend instance based on environment settings."""
    global _METRICS_BACKEND
    if _METRICS_BACKEND is not None:
        return _METRICS_BACKEND

    backend_name = os.getenv("AETHER_METRICS_BACKEND", "none").lower()
    if backend_name == "prometheus":
        port = int(os.getenv("AETHER_PROMETHEUS_PORT", "9400"))
        try:
            _METRICS_BACKEND = PrometheusMetricsBackend(port=port)
        except RuntimeError as exc:
            logger.warning("Prometheus backend unavailable: %s", exc)
            _METRICS_BACKEND = NullMetricsBackend()
    else:
        _METRICS_BACKEND = NullMetricsBackend()

    return _METRICS_BACKEND
