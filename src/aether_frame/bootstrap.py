# -*- coding: utf-8 -*-
"""
Bootstrap - System Initialization Manager

Single-file initialization system for Aether Frame that coordinates
the startup of core system components with proper dependency management.
"""

import logging
from typing import NamedTuple, Optional
from datetime import datetime

from .agents.manager import AgentManager
from .config.settings import Settings
from .contracts import AgentConfig, FrameworkType
from .execution.execution_engine import ExecutionEngine
from .execution.task_router import TaskRouter
from .framework.framework_registry import FrameworkRegistry
from .tools.service import ToolService

logger = logging.getLogger(__name__)


class SystemComponents(NamedTuple):
    """Container for initialized system components."""

    framework_registry: FrameworkRegistry
    agent_manager: AgentManager
    task_router: TaskRouter
    execution_engine: ExecutionEngine
    tool_service: Optional[ToolService] = None


async def initialize_system(settings: Optional[Settings] = None) -> SystemComponents:
    """
    Initialize all system components with proper dependency order.

    Args:
        settings: Application settings (loads defaults if None)

    Returns:
        SystemComponents: Container with all initialized components

    Raises:
        RuntimeError: If critical components fail to initialize
    """
    if settings is None:
        settings = Settings()
    
    logger.info("Starting Aether Frame system initialization...")

    try:
        # Phase 1: Framework Registry 
        logger.info("Phase 1: Initializing Framework Registry...")
        framework_registry = FrameworkRegistry()
        logger.info(f"Framework registry created - type: {type(framework_registry).__name__}")

        # Phase 2: Tool Service (create first for adapter integration)
        tool_service = None
        if getattr(settings, "enable_tool_service", True):
            logger.info("Phase 2: Initializing Tool Service...")
            tool_service = ToolService()
            tool_config = {
                "enable_mcp": getattr(settings, "enable_mcp_tools", False),
                "enable_adk_native": getattr(
                    settings, "enable_adk_native_tools", False
                ),
                "enable_builtin": True,
            }
            await tool_service.initialize(tool_config)
            logger.info(f"Tool Service initialized - config: {tool_config}")
        else:
            logger.info("Tool Service disabled in configuration")

        # Phase 3: ADK Adapter (with tool service integration)
        # ADK adapter auto-initialization happens here
        # FrameworkRegistry.get_adapter(ADK) triggers auto-load
        # AdkFrameworkAdapter.initialize() handles ADK runtime setup with strong dependency checking
        logger.info("Phase 3: Loading ADK framework adapter with tool integration...")
        try:
            adk_adapter = await framework_registry.get_adapter(FrameworkType.ADK)
            # Initialize with tool service integration and settings
            if adk_adapter:
                await adk_adapter.initialize(config=None, tool_service=tool_service, settings=settings)
                logger.info(f"ADK framework adapter loaded successfully - type: {type(adk_adapter).__name__}")
            else:
                raise RuntimeError("Failed to load ADK framework adapter")
        except Exception as e:
            logger.error(f"ADK framework adapter failed to load: {str(e)}")
            # ADK is required - fail the bootstrap process
            raise RuntimeError(
                f"System cannot start without ADK framework: {str(e)}"
            ) from e

        # Phase 4: Agent Manager
        logger.info("Phase 4: Initializing Agent Manager...")
        agent_manager = AgentManager()

        # TODO: Agent factory registration will be implemented later
        # For now, AgentManager uses direct if/elif logic in _create_domain_agent
        logger.info("Agent Manager initialized - detection method: direct_framework_check")

        # Phase 5: Execution components
        logger.info("Phase 5: Initializing Execution Components...")
        task_router = TaskRouter(settings)
        execution_engine = ExecutionEngine(framework_registry, settings)
        logger.info("Execution components initialized - task_router, execution_engine created")

        logger.info("System initialization completed successfully - 5 phases, 5 components")

        return SystemComponents(
            framework_registry=framework_registry,
            agent_manager=agent_manager,
            task_router=task_router,
            execution_engine=execution_engine,
            tool_service=tool_service,
        )

    except Exception as e:
        logger.error(f"System initialization failed: {str(e)}")
        raise RuntimeError(f"System initialization failed: {str(e)}")


async def _register_adk_agent_factory(agent_manager: AgentManager):
    """
    Placeholder function for ADK agent factory registration.

    This function is currently not used since AgentManager doesn't have
    register_agent_factory method implemented yet. When the factory pattern
    is implemented, this function can be used.
    """
    # TODO: Implement when AgentManager.register_agent_factory is available
    logger.info("ADK agent factory registration skipped (not implemented yet)")
    pass


async def create_ai_assistant(settings: Optional[Settings] = None):
    """
    Create fully initialized AI Assistant - primary external interface.

    This is the main function applications should use to get a ready-to-use
    AI Assistant instance with all dependencies properly initialized.

    Args:
        settings: Optional application settings

    Returns:
        AIAssistant: Fully initialized AI Assistant ready for use

    Example:
        >>> assistant = await create_ai_assistant()
        >>> result = await assistant.process_request(task_request)
    """
    from .execution.ai_assistant import AIAssistant

    # Initialize all system components
    components = await initialize_system(settings)

    # Create AI Assistant with initialized components
    return AIAssistant(
        execution_engine=components.execution_engine, settings=settings or Settings()
    )


async def create_system_components(
    settings: Optional[Settings] = None,
) -> SystemComponents:
    """
    Create system components for advanced usage or testing.

    This function provides direct access to system components for:
    - Advanced integrations that need component-level control
    - Testing scenarios that need to mock specific components
    - Custom applications that want to build their own orchestration

    Args:
        settings: Optional application settings

    Returns:
        SystemComponents: All initialized system components

    Example:
        >>> components = await create_system_components()
        >>> result = await components.execution_engine.execute_task(task_request)
    """
    return await initialize_system(settings)


async def health_check_system(components: SystemComponents) -> dict:
    """
    Perform comprehensive system health check.

    Args:
        components: System components to check

    Returns:
        dict: Health status of all components
    """
    health_status = {"overall_status": "healthy", "components": {}}

    try:
        # Framework registry health
        available_frameworks = (
            await components.framework_registry.get_available_frameworks()
        )
        health_status["components"]["framework_registry"] = {
            "status": "healthy",
            "available_frameworks": [fw.value for fw in available_frameworks],
        }

        # Tool service health (if enabled)
        if components.tool_service:
            tool_health = await components.tool_service.health_check()
            health_status["components"]["tool_service"] = tool_health
        else:
            health_status["components"]["tool_service"] = {"status": "disabled"}

        # Agent manager health
        agent_count = len(await components.agent_manager.list_agents())
        health_status["components"]["agent_manager"] = {
            "status": "healthy",
            "active_agents": agent_count,
        }

        # Execution engine health
        health_status["components"]["execution_engine"] = {"status": "healthy"}

        # Task router health
        health_status["components"]["task_router"] = {"status": "healthy"}

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        health_status["overall_status"] = "unhealthy"
        health_status["error"] = str(e)

    return health_status


async def shutdown_system(components: SystemComponents):
    """
    Gracefully shutdown all system components.

    Args:
        components: System components to shutdown
    """
    logger.info("Starting system shutdown...")

    try:
        # Shutdown in reverse order of initialization

        # Shutdown tool service
        if components.tool_service:
            await components.tool_service.shutdown()
            logger.info("Tool service shutdown completed")

        # Shutdown agent manager
        try:
            agents = await components.agent_manager.list_agents()
            for agent_id in agents:
                await components.agent_manager.destroy_agent(agent_id)
            logger.info("Agent manager shutdown completed")
        except Exception as e:
            logger.warning(f"Agent manager shutdown warning: {str(e)}")

        # Shutdown framework registry
        await components.framework_registry.shutdown_all_adapters()
        logger.info("Framework registry shutdown completed")

        logger.info("System shutdown completed successfully")

    except Exception as e:
        logger.error(f"System shutdown error: {str(e)}")
        # Don't re-raise, as this is cleanup code
