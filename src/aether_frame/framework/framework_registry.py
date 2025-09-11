# -*- coding: utf-8 -*-
"""Framework Registry - Management of framework adapters."""

from typing import Dict, List, Optional

from ..contracts import FrameworkType
from ..framework.base.framework_adapter import FrameworkAdapter


class FrameworkRegistry:
    """
    FrameworkRegistry manages the registration and lifecycle of framework adapters,
    providing a unified interface for framework discovery and access.
    """

    def __init__(self):
        """Initialize framework registry."""
        self._adapters: Dict[FrameworkType, FrameworkAdapter] = {}
        self._adapter_configs: Dict[FrameworkType, dict] = {}
        self._initialization_status: Dict[FrameworkType, bool] = {}

    def register_adapter(
        self,
        framework_type: FrameworkType,
        adapter: FrameworkAdapter,
        config: Optional[dict] = None,
    ):
        """
        Register a framework adapter.

        Args:
            framework_type: Type of framework being registered
            adapter: The framework adapter instance
            config: Optional configuration for the adapter
        """
        self._adapters[framework_type] = adapter
        self._adapter_configs[framework_type] = config or {}
        self._initialization_status[framework_type] = False

    async def get_adapter(
        self, framework_type: FrameworkType
    ) -> Optional[FrameworkAdapter]:
        """
        Get a framework adapter by type.

        Args:
            framework_type: Type of framework adapter to retrieve

        Returns:
            FrameworkAdapter: The requested adapter or None if not available
        """
        if framework_type not in self._adapters:
            # Try to auto-load the adapter
            await self._auto_load_adapter(framework_type)

        adapter = self._adapters.get(framework_type)
        if adapter and not self._initialization_status.get(framework_type, False):
            await self._initialize_adapter(framework_type, adapter)

        return adapter

    async def get_available_frameworks(self) -> List[FrameworkType]:
        """Get list of available framework types."""
        available = []
        for framework_type in FrameworkType:
            try:
                adapter = await self.get_adapter(framework_type)
                if adapter and await adapter.is_available():
                    available.append(framework_type)
            except Exception:
                # Skip unavailable frameworks
                continue
        return available

    async def initialize_all_adapters(self):
        """Initialize all registered adapters."""
        for framework_type, adapter in self._adapters.items():
            if not self._initialization_status.get(framework_type, False):
                await self._initialize_adapter(framework_type, adapter)

    async def shutdown_all_adapters(self):
        """Shutdown all registered adapters."""
        for framework_type, adapter in self._adapters.items():
            try:
                await adapter.shutdown()
                self._initialization_status[framework_type] = False
            except Exception:
                # Log error but continue with other adapters
                pass

    async def _auto_load_adapter(self, framework_type: FrameworkType):
        """Auto-load adapter for the specified framework type with capability config."""
        try:
            if framework_type == FrameworkType.ADK:
                from ..config.framework_capabilities import (
                    get_framework_capability_config,
                )
                from ..framework.adk.adk_adapter import AdkFrameworkAdapter

                adapter = AdkFrameworkAdapter()
                # Get static capability configuration for ADK
                capability_config = get_framework_capability_config(framework_type)
                # Convert to dict for registration
                config = {
                    "capabilities": capability_config,
                    "async_execution": capability_config.async_execution,
                    "memory_management": capability_config.memory_management,
                    "observability": capability_config.observability,
                    "streaming": capability_config.streaming,
                    "execution_modes": capability_config.execution_modes,
                    "default_timeout": capability_config.default_timeout,
                    "max_iterations": capability_config.max_iterations,
                    **capability_config.extra_config,
                }
                self.register_adapter(framework_type, adapter, config)
            elif framework_type == FrameworkType.AUTOGEN:
                # Future implementation with capability config
                pass
            elif framework_type == FrameworkType.LANGGRAPH:
                # Future implementation with capability config
                pass
        except ImportError:
            # Framework not available
            pass
        except ValueError as e:
            # Capability configuration not found
            print(f"Warning: {e}")
            pass

    async def _initialize_adapter(
        self, framework_type: FrameworkType, adapter: FrameworkAdapter
    ):
        """Initialize a specific adapter."""
        try:
            config = self._adapter_configs.get(framework_type, {})
            await adapter.initialize(config)
            self._initialization_status[framework_type] = True
        except Exception as e:
            # Log initialization error
            self._initialization_status[framework_type] = False
            raise e

    def get_adapter_status(self, framework_type: FrameworkType) -> dict:
        """Get status information for a framework adapter."""
        return {
            "registered": framework_type in self._adapters,
            "initialized": self._initialization_status.get(framework_type, False),
            "config": self._adapter_configs.get(framework_type, {}),
        }
