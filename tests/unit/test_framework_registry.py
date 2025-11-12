# -*- coding: utf-8 -*-
"""Unit tests for FrameworkRegistry lifecycle handling."""

from unittest.mock import AsyncMock

import pytest

from aether_frame.contracts import ExecutionContext, FrameworkType, TaskRequest, TaskResult
from aether_frame.framework.base.framework_adapter import FrameworkAdapter
from aether_frame.framework.framework_registry import FrameworkRegistry


class StubAdapter(FrameworkAdapter):
    def __init__(self, framework_type: FrameworkType):
        self._framework_type = framework_type
        self.initialized = False
        self.shutdown_called = False
        self.config_received = None

    @property
    def framework_type(self) -> FrameworkType:
        return self._framework_type

    async def initialize(self, config=None):
        self.initialized = True
        self.config_received = config or {}

    async def execute_task(self, task_request: TaskRequest, strategy):
        raise NotImplementedError

    async def execute_task_live(self, task_request: TaskRequest, context: ExecutionContext):
        raise NotImplementedError

    async def shutdown(self):
        self.shutdown_called = True

    async def get_capabilities(self):
        return {}

    async def health_check(self):
        return {"status": "ok"}

    async def is_available(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_get_adapter_initializes_on_first_use(monkeypatch):
    registry = FrameworkRegistry()
    adapter = StubAdapter(FrameworkType.AUTOGEN)
    registry.register_adapter(FrameworkType.AUTOGEN, adapter, config={"foo": "bar"})

    monkeypatch.setattr(registry, "_auto_load_adapter", AsyncMock())

    retrieved = await registry.get_adapter(FrameworkType.AUTOGEN)

    assert retrieved is adapter
    assert adapter.initialized is True
    assert adapter.config_received == {"foo": "bar"}


@pytest.mark.asyncio
async def test_initialize_and_shutdown_all_adapters(monkeypatch):
    registry = FrameworkRegistry()
    auto_adapter = StubAdapter(FrameworkType.AUTOGEN)
    registry.register_adapter(FrameworkType.AUTOGEN, auto_adapter)

    lang_adapter = StubAdapter(FrameworkType.LANGGRAPH)
    registry.register_adapter(FrameworkType.LANGGRAPH, lang_adapter)

    monkeypatch.setattr(registry, "_auto_load_adapter", AsyncMock())

    await registry.initialize_all_adapters()

    assert auto_adapter.initialized
    assert lang_adapter.initialized

    await registry.shutdown_all_adapters()

    assert auto_adapter.shutdown_called
    assert lang_adapter.shutdown_called


@pytest.mark.asyncio
async def test_get_available_frameworks_filters_by_availability(monkeypatch):
    registry = FrameworkRegistry()
    available_adapter = StubAdapter(FrameworkType.LANGGRAPH)
    available_adapter.is_available = AsyncMock(return_value=True)
    registry.register_adapter(FrameworkType.LANGGRAPH, available_adapter)

    unavailable_adapter = StubAdapter(FrameworkType.AUTOGEN)
    unavailable_adapter.is_available = AsyncMock(return_value=False)
    registry.register_adapter(FrameworkType.AUTOGEN, unavailable_adapter)

    monkeypatch.setattr(registry, "_auto_load_adapter", AsyncMock())

    frameworks = await registry.get_available_frameworks()

    assert FrameworkType.LANGGRAPH in frameworks
    assert FrameworkType.AUTOGEN not in frameworks
