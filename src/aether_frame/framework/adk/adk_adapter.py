# -*- coding: utf-8 -*-
"""ADK Framework Adapter Implementation."""

from typing import Any, Dict, List, Optional, AsyncIterator, TYPE_CHECKING

from ...agents.manager import AgentManager
from ...contracts import (
    AgentRequest,
    ExecutionContext,
    FrameworkType,
    LiveExecutionResult,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskStreamChunk,
    TaskChunkType,
)
from ...execution.task_router import ExecutionStrategy
from ..base.framework_adapter import FrameworkAdapter
from .live_communicator import AdkLiveCommunicator

if TYPE_CHECKING:
    # ADK imports for type checking only
    try:
        from google.adk.runners import InMemoryRunner, LiveRequestQueue
        from google.adk.sessions import Session
        from google.adk.agents.run_config import RunConfig
        from google.adk.events import Event as AdkEvent
    except ImportError:
        InMemoryRunner = Any
        LiveRequestQueue = Any
        Session = Any
        RunConfig = Any
        AdkEvent = Any


class AdkFrameworkAdapter(FrameworkAdapter):
    """
    Framework adapter for Google Cloud Agent Development Kit (ADK).

    Provides integration with ADK's agent execution, memory management,
    and observability features through the unified framework interface.
    """

    def __init__(self):
        """Initialize ADK framework adapter."""
        self._initialized = False
        self._config = {}
        self._agent_manager: Optional[AgentManager] = None
        self._client = None

    @property
    def framework_type(self) -> FrameworkType:
        """Return ADK framework type."""
        return FrameworkType.ADK

    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize ADK framework adapter.

        Args:
            config: ADK-specific configuration including project, location,
            etc.
        """
        self._config = config or {}

        # Initialize ADK client
        try:
            # Import ADK dependencies
            # TODO: Add actual ADK client initialization
            # from google.cloud import adk
            # self._client = adk.Client(
            #     project=self._config.get('project'),
            #     location=self._config.get('location')
            # )

            # Initialize agent manager
            self._agent_manager = AgentManager()

            self._initialized = True
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ADK: {str(e)}")

    async def execute_task(
        self, task_request: TaskRequest, strategy: ExecutionStrategy
    ) -> TaskResult:
        """
        Execute a task through ADK framework coordination.

        ADK framework uses single-agent execution patterns as specified in
        strategy. This adapter coordinates the execution flow and converts
        between data layers.

        Args:
            task_request: The universal task request
            strategy: Execution strategy containing framework type and
            execution mode

        Returns:
            TaskResult: The result of task execution
        """
        if not self._initialized:
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message="ADK framework not initialized",
            )

        try:
            # Convert TaskRequest to AgentRequest (protocol conversion only)
            agent_request = self._convert_task_to_agent_request(
                task_request, strategy
            )

            # Ensure agent manager is available
            if not self._agent_manager:
                raise RuntimeError("Agent manager not initialized")

            # Delegate to AgentManager - it handles agent lifecycle
            agent_response = await self._agent_manager.execute_agent(
                agent_request
            )

            # Convert agent response back to task result (protocol conversion)
            return TaskResult(
                task_id=task_request.task_id,
                status=(
                    TaskStatus.SUCCESS
                    if agent_response.task_result
                    else TaskStatus.ERROR
                ),
                result_data=(
                    agent_response.task_result.result_data
                    if agent_response.task_result
                    else None
                ),
                messages=(
                    agent_response.task_result.messages
                    if agent_response.task_result
                    else []
                ),
                execution_context=task_request.execution_context,
                error_message=agent_response.error_details,
                metadata=agent_response.metadata,
            )

        except Exception as e:
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"ADK coordination failed: {str(e)}",
            )

    async def is_available(self) -> bool:
        """Check if ADK framework is available."""
        try:
            # Check ADK dependencies and client connectivity
            # TODO: Add actual ADK availability check
            return self._initialized
        except Exception:
            return False

    async def get_capabilities(self) -> List[str]:
        """Get ADK framework capabilities."""
        return [
            "conversational_agents",
            "memory_management",
            "observability",
            "tool_integration",
            "session_management",
            "state_persistence",
        ]

    async def health_check(self) -> Dict[str, Any]:
        """Perform ADK framework health check."""
        return {
            "framework": "adk",
            "status": "healthy" if self._initialized else "not_initialized",
            "version": "1.0.0",  # TODO: Get actual ADK version
            "capabilities": await self.get_capabilities(),
            "active_agents": (
                len(await self._agent_manager.list_agents())
                if self._agent_manager
                else 0
            ),
        }

    async def shutdown(self):
        """Shutdown ADK framework adapter."""
        # Cleanup all agents through agent manager
        if self._agent_manager:
            agents = await self._agent_manager.list_agents()
            for agent_id in agents:
                await self._agent_manager.destroy_agent(agent_id)

        # Cleanup ADK client
        if self._client:
            # TODO: Add actual ADK client cleanup
            self._client = None

        self._initialized = False

    # TODO: Future enhancement - Add support for configurable Runner types
    # Currently using InMemoryRunner for simplicity, but could extend to:
    # - VertexAiRunner for production Google Cloud deployments
    # - DatabaseRunner for custom persistent storage
    # - Configuration-driven runner selection based on deployment environment
    async def execute_task_live(
        self, task_request: TaskRequest, context: ExecutionContext
    ) -> LiveExecutionResult:
        """
        Execute a task in live/interactive mode with real-time bidirectional communication.
        
        This method implements ADK's live execution pattern using run_live() to enable
        interactive workflows such as tool approval, user input requests, and real-time
        cancellation. It uses InMemoryRunner for simplicity but can be extended to support
        other Runner types based on deployment needs.
        
        Args:
            task_request: The universal task request
            context: Execution context with user and session information
            
        Returns:
            LiveExecutionResult: Tuple of (event_stream, communicator) where:
                - event_stream: AsyncIterator[TaskStreamChunk] for real-time events
                - communicator: AdkLiveCommunicator for bidirectional communication
                
        Raises:
            RuntimeError: If ADK framework not initialized or execution fails
        """
        if not self._initialized:
            raise RuntimeError("ADK framework not initialized")
            
        try:
            # Import ADK components at runtime to avoid import errors
            from google.adk.runners import InMemoryRunner, LiveRequestQueue
            from google.adk.agents.run_config import RunConfig, StreamingMode
            from google.adk import Agent
            
            # Use conversion methods to create proper ADK configuration
            session_config = self._convert_contexts_to_session_config(task_request)
            agent_config = self._convert_task_request_to_agent_config(task_request)
            run_config = self._convert_execution_context_to_run_config(context)
            
            # Create ADK Agent using converted configuration
            agent = Agent(**agent_config)
            
            # Extract app_name from session config
            app_name = session_config["app_name"]
            
            # Create InMemoryRunner - TODO: Support other runner types via configuration
            # Current implementation uses InMemoryRunner for development/testing
            # Future versions should support:
            # - VertexAiRunner for production Google Cloud deployments
            # - Custom runners based on configuration
            runner = InMemoryRunner(app_name=app_name, agent=agent)
            
            # Create session for this live execution using comprehensive session config
            session = await runner.session_service.create_session(
                app_name=session_config["app_name"],
                user_id=session_config["user_id"],
                session_id=session_config.get("session_id"),  # May be None for new sessions
                state=session_config.get("initial_state", {})  # Comprehensive state integration using correct parameter name
            )
            
            # Create LiveRequestQueue for bidirectional communication
            live_request_queue = LiveRequestQueue()
            
            # Start live execution
            # This returns an async iterator of ADK events that need to be converted
            # to our unified TaskStreamChunk format
            adk_live_events = runner.run_live(
                session=session,
                live_request_queue=live_request_queue,
                run_config=run_config
            )
            
            # Send initial message from TaskRequest to start the conversation
            if task_request.messages:
                # Extract the latest user message
                user_message = None
                for msg in reversed(task_request.messages):
                    if hasattr(msg, 'role') and msg.role == 'user':
                        user_message = msg.content
                        break
                    elif isinstance(msg, dict) and msg.get('role') == 'user':
                        user_message = msg.get('content', '')
                        break
                
                if user_message:
                    # Send user message to ADK agent
                    from google.genai.types import Content, Part
                    content = Content(parts=[Part(text=user_message)])
                    live_request_queue.send_content(content)
            elif task_request.description:
                # Fallback to task description
                from google.genai.types import Content, Part
                content = Content(parts=[Part(text=task_request.description)])
                live_request_queue.send_content(content)
            
            # Create our live communicator wrapper
            communicator = AdkLiveCommunicator(live_request_queue)
            
            # Create event stream that converts ADK events to TaskStreamChunks
            async def event_stream() -> AsyncIterator[TaskStreamChunk]:
                """
                Convert ADK events to unified TaskStreamChunk format.
                
                This async generator processes the stream of ADK events and converts
                them to our standardized TaskStreamChunk format for framework-agnostic
                consumption by the execution engine.
                """
                sequence_id = 0
                
                try:
                    async for adk_event in adk_live_events:
                        # Convert ADK event to our unified format
                        chunk = self._convert_adk_event_to_chunk(
                            adk_event, task_request.task_id, sequence_id
                        )
                        
                        if chunk:  # Only yield valid chunks
                            yield chunk
                            sequence_id += 1
                            
                except Exception as e:
                    # Yield error chunk if something goes wrong
                    yield TaskStreamChunk(
                        task_id=task_request.task_id,
                        chunk_type=TaskChunkType.ERROR,
                        sequence_id=sequence_id,
                        content=f"Live execution error: {str(e)}",
                        is_final=True,
                        metadata={"error_type": "live_execution_error"}
                    )
                finally:
                    # Ensure communicator is properly closed
                    communicator.close()
            
            # Return the live execution result tuple
            return (event_stream(), communicator)
            
        except ImportError as e:
            raise RuntimeError(f"ADK dependencies not available: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to start live execution: {str(e)}")

    def _convert_execution_context_to_run_config(self, context: ExecutionContext):
        """
        Convert ExecutionContext to ADK RunConfig (runtime behavior configuration).
        
        Maps execution context parameters to ADK's runtime configuration for
        controlling agent execution behavior, streaming modes, and limits.
        
        Args:
            context: The execution context containing runtime parameters
            
        Returns:
            RunConfig: ADK runtime configuration object
        """
        from google.adk.agents.run_config import RunConfig, StreamingMode
        
        # Map execution mode to streaming mode
        streaming_mode = StreamingMode.BIDI  # Default to bidirectional for live execution
        if context.execution_mode == "sync":
            streaming_mode = StreamingMode.NONE
        elif context.execution_mode == "async":
            streaming_mode = StreamingMode.BIDI
            
        # Configure response modalities
        response_modalities = ["TEXT"]  # Default to text
        if context.metadata.get("support_audio", False):
            response_modalities.append("AUDIO")
            
        return RunConfig(
            response_modalities=response_modalities,
            streaming_mode=streaming_mode,
            max_llm_calls=context.metadata.get("max_llm_calls", 100),
            save_input_blobs_as_artifacts=context.metadata.get("save_artifacts", False)
        )
    
    def _convert_contexts_to_session_config(self, task_request: TaskRequest) -> Dict[str, Any]:
        """
        Convert TaskRequest contexts to comprehensive ADK Session configuration.
        
        Builds complete initial state by integrating all context information:
        user preferences, session history, execution metadata, and knowledge sources.
        
        Args:
            task_request: The task request containing multiple contexts
            
        Returns:
            Dict containing comprehensive session configuration
        """
        # Build comprehensive initial state integrating all contexts
        initial_state = {
            # Core task information
            "task_id": task_request.task_id,
            "task_type": task_request.task_type,
            "task_description": task_request.description or "",
        }
        
        # User context integration
        if task_request.user_context:
            user_context = task_request.user_context
            initial_state.update({
                "user_id": user_context.user_id,
                "user_name": getattr(user_context, 'user_name', ''),
            })
            
            # User preferences with prefix to avoid conflicts
            user_prefs = getattr(user_context, 'preferences', None)
            if user_prefs:
                initial_state.update({
                    f"user_pref_{k}": v for k, v in user_prefs.items()
                })
            
            # User permissions for tool access control
            user_permissions = getattr(user_context, 'permissions', None)
            if user_permissions:
                initial_state["user_permissions"] = user_permissions
        
        # Session context integration
        if task_request.session_context:
            session_ctx = task_request.session_context
            initial_state.update({
                "session_id": session_ctx.session_id,
            })
            
            # Existing session state (safely)
            if hasattr(session_ctx, 'session_state') and session_ctx.session_state:
                initial_state.update(session_ctx.session_state)
            
            # Conversation history for context continuity
            if hasattr(session_ctx, 'conversation_history') and session_ctx.conversation_history:
                initial_state["conversation_history"] = [
                    {"role": msg.role, "content": msg.content} 
                    for msg in session_ctx.conversation_history
                ]
            
            # Session context variables (safely)
            context_vars = getattr(session_ctx, 'context_variables', None)
            if context_vars:
                initial_state.update({
                    f"session_{k}": v for k, v in context_vars.items()
                })
        
        # Execution context integration
        if task_request.execution_context:
            exec_ctx = task_request.execution_context
            initial_state.update({
                "execution_id": exec_ctx.execution_id,
                "trace_id": exec_ctx.trace_id or "",
                "execution_mode": exec_ctx.execution_mode,
                # Execution metadata
                **{f"exec_{k}": v for k, v in exec_ctx.metadata.items()}
            })
        
        # Knowledge sources integration
        if task_request.available_knowledge:
            initial_state["knowledge_sources"] = [
                {
                    "id": kb.knowledge_id,
                    "type": kb.knowledge_type,
                    "source": kb.source,
                    "metadata": kb.metadata
                }
                for kb in task_request.available_knowledge
            ]
        
        # Task metadata integration
        if task_request.metadata:
            initial_state.update({
                f"meta_{k}": v for k, v in task_request.metadata.items()
            })
        
        # Extract core session parameters
        user_id = "anonymous"
        if task_request.user_context:
            user_id = task_request.user_context.get_adk_user_id()
        
        session_id = None
        if task_request.session_context:
            session_id = getattr(task_request.session_context, 'session_id', None)
        
        return {
            "app_name": f"aether_frame_{task_request.task_id}",
            "user_id": user_id,
            "session_id": session_id,
            "initial_state": initial_state
        }
        
    def _convert_task_request_to_agent_config(self, task_request: TaskRequest) -> Dict[str, Any]:
        """
        Convert TaskRequest to comprehensive ADK Agent configuration.
        
        Maps task information, tools, and capabilities to ADK Agent constructor
        parameters, integrating strategy-driven model selection and intelligent
        instruction building.
        
        Args:
            task_request: The task request containing agent requirements
            
        Returns:
            Dict containing comprehensive agent configuration parameters
        """
        # Extract model from execution config or use default
        model = self._extract_model_configuration(task_request)
        
        # Build comprehensive system instruction
        instruction_parts = []
        
        # Base instruction based on task type
        task_type_instructions = {
            "chat": "You are a conversational AI assistant designed to help users with their questions and tasks.",
            "analysis": "You are an analytical AI assistant specialized in data analysis and insights.",
            "coding": "You are a coding AI assistant that helps with programming tasks and technical questions.",
            "creative": "You are a creative AI assistant that helps with writing, brainstorming, and creative tasks."
        }
        base_instruction = task_type_instructions.get(
            task_request.task_type, 
            f"You are an AI assistant handling {task_request.task_type} tasks."
        )
        instruction_parts.append(base_instruction)
        
        # Add task-specific context
        if task_request.description:
            instruction_parts.append(f"Current task: {task_request.description}")
        
        # Add user preferences if available
        if task_request.user_context and hasattr(task_request.user_context, 'preferences'):
            user_prefs = task_request.user_context.preferences
            if user_prefs:
                pref_parts = []
                if user_prefs.get('communication_style'):
                    pref_parts.append(f"communication style: {user_prefs['communication_style']}")
                if user_prefs.get('detail_level'):
                    pref_parts.append(f"detail level: {user_prefs['detail_level']}")
                if user_prefs.get('language'):
                    pref_parts.append(f"preferred language: {user_prefs['language']}")
                
                if pref_parts:
                    instruction_parts.append(f"User preferences: {', '.join(pref_parts)}")
        
        # Add knowledge sources context
        if task_request.available_knowledge:
            knowledge_desc = []
            for kb in task_request.available_knowledge:
                knowledge_desc.append(f"{kb.knowledge_type} from {kb.source}")
            
            if knowledge_desc:
                instruction_parts.append(
                    f"You have access to the following knowledge sources: {', '.join(knowledge_desc)}"
                )
        
        # Add tool usage instructions
        if task_request.available_tools:
            tools_desc = [tool.name for tool in task_request.available_tools]
            instruction_parts.append(
                f"You have access to the following tools: {', '.join(tools_desc)}. "
                "Use them appropriately to complete tasks effectively."
            )
        else:
            # Add echo tool for testing when no real tools available
            instruction_parts.append(
                "You have access to an echo tool for testing. Use it when users ask you to repeat or echo messages."
            )
        
        # Extract execution config instructions
        if (task_request.execution_config and 
            isinstance(task_request.execution_config, dict) and 
            task_request.execution_config.get('system_instruction')):
            instruction_parts.append(task_request.execution_config['system_instruction'])
        
        # Build agent tools
        agent_tools = self._convert_available_tools_to_adk(task_request)
        
        # Create safe agent name
        safe_task_id = task_request.task_id.replace('-', '_').replace(':', '_')[:8]
        
        return {
            "name": f"agent_{safe_task_id}",
            "model": model,
            "description": f"ADK agent for {task_request.task_type}: {task_request.description or 'task execution'}",
            "instruction": "\n\n".join(instruction_parts),
            "tools": agent_tools
        }
    
    def _extract_model_configuration(self, task_request: TaskRequest) -> str:
        """
        Extract model configuration from task request and execution config.
        
        Priority order:
        1. execution_config.model
        2. task metadata model
        3. user preferences model
        4. default model
        """
        # Check execution config first
        if (task_request.execution_config and 
            isinstance(task_request.execution_config, dict) and 
            task_request.execution_config.get('model')):
            return task_request.execution_config['model']
        
        # Check task metadata
        if task_request.metadata and task_request.metadata.get('preferred_model'):
            return task_request.metadata['preferred_model']
        
        # Check user preferences
        if (task_request.user_context and 
            hasattr(task_request.user_context, 'preferences') and 
            task_request.user_context.preferences.get('preferred_model')):
            return task_request.user_context.preferences['preferred_model']
        
        # Default model based on task type
        task_type_models = {
            "coding": "gemini-1.5-pro",
            "analysis": "gemini-1.5-pro", 
            "creative": "gemini-1.5-flash",
            "chat": "gemini-1.5-flash"
        }
        
        return task_type_models.get(task_request.task_type, "gemini-1.5-flash")
    
    def _convert_available_tools_to_adk(self, task_request: TaskRequest) -> list:
        """
        Convert TaskRequest.available_tools to ADK-compatible function tools.
        
        Args:
            task_request: Task request containing available tools
            
        Returns:
            List of ADK-compatible function tools
        """
        adk_tools = []
        
        if task_request.available_tools:
            for available_tool in task_request.available_tools:
                # TODO: Implement proper tool conversion based on tool type
                # For now, this is a placeholder for the conversion logic
                # Will convert available_tool to ADK function format
                _ = available_tool  # Acknowledge the variable to avoid unused warning
                pass
        
        # Always add echo tool for testing/debugging
        def echo_tool(message: str) -> dict:
            """Echo the input message back to the user.
            
            Args:
                message (str): The message to echo back
                
            Returns:
                dict: Response with echoed message
            """
            return {
                "status": "success",
                "echoed_message": f"Echo: {message}",
                "original_message": message
            }
        
        adk_tools.append(echo_tool)
        return adk_tools

    def _convert_adk_event_to_chunk(
        self, adk_event: "AdkEvent", task_id: str, sequence_id: int
    ) -> Optional[TaskStreamChunk]:
        """
        Convert an ADK Event to our unified TaskStreamChunk format.
        
        This method handles the translation between ADK's event system and our
        framework-agnostic TaskStreamChunk format. It maps different types of
        ADK events to appropriate TaskChunkType values.
        
        Args:
            adk_event: The ADK event to convert
            task_id: The task ID for this execution
            sequence_id: Sequential ID for this chunk
            
        Returns:
            TaskStreamChunk if the event should be exposed, None if it should be filtered
            
        TODO: Future enhancements for event conversion:
        1. Better mapping of ADK event types to TaskChunkType
        2. Support for tool approval scenarios
        3. Enhanced metadata extraction from ADK events
        4. Better handling of streaming vs final responses
        """
        try:
            # Handle text content from agent responses
            if (hasattr(adk_event, 'content') and adk_event.content and 
                hasattr(adk_event.content, 'parts') and adk_event.content.parts):
                
                first_part = adk_event.content.parts[0]
                
                # Handle text responses
                if hasattr(first_part, 'text') and first_part.text:
                    # Determine if this is partial or final content
                    is_partial = getattr(adk_event, 'partial', False)
                    
                    return TaskStreamChunk(
                        task_id=task_id,
                        chunk_type=TaskChunkType.RESPONSE if not is_partial else TaskChunkType.PROGRESS,
                        sequence_id=sequence_id,
                        content=first_part.text,
                        is_final=not is_partial,
                        metadata={
                            "author": getattr(adk_event, 'author', 'agent'),
                            "adk_event_id": getattr(adk_event, 'id', ''),
                            "turn_complete": getattr(adk_event, 'turn_complete', False)
                        }
                    )
                
                # TODO: Future enhancement - Handle function calls for tool approval
                # Currently not implemented, but should handle:
                # - Tool call requests -> TaskChunkType.TOOL_CALL_REQUEST
                # - Tool approval requests -> TaskChunkType.TOOL_APPROVAL_REQUEST
                # - Function responses -> TaskChunkType.RESPONSE
                
                # Handle function calls (tool requests)
                if hasattr(first_part, 'function_call') and first_part.function_call:
                    return TaskStreamChunk(
                        task_id=task_id,
                        chunk_type=TaskChunkType.TOOL_CALL_REQUEST,
                        sequence_id=sequence_id,
                        content={
                            "function_name": first_part.function_call.name,
                            "arguments": first_part.function_call.args
                        },
                        is_final=False,
                        metadata={
                            "author": getattr(adk_event, 'author', 'agent'),
                            "requires_approval": True  # TODO: Make this configurable
                        }
                    )
            
            # Handle turn completion and other control signals
            if hasattr(adk_event, 'turn_complete') and adk_event.turn_complete:
                return TaskStreamChunk(
                    task_id=task_id,
                    chunk_type=TaskChunkType.COMPLETE,
                    sequence_id=sequence_id,
                    content="Turn completed",
                    is_final=True,
                    metadata={
                        "author": getattr(adk_event, 'author', 'agent')
                    }
                )
            
            # Handle errors
            if hasattr(adk_event, 'error_code') and adk_event.error_code:
                return TaskStreamChunk(
                    task_id=task_id,
                    chunk_type=TaskChunkType.ERROR,
                    sequence_id=sequence_id,
                    content=getattr(adk_event, 'error_message', 'Unknown error'),
                    is_final=True,
                    metadata={
                        "error_code": adk_event.error_code,
                        "author": getattr(adk_event, 'author', 'system')
                    }
                )
            
            # Filter out events that don't need to be exposed
            # (e.g., internal state updates, metadata events)
            return None
            
        except Exception as e:
            # If event conversion fails, create an error chunk
            return TaskStreamChunk(
                task_id=task_id,
                chunk_type=TaskChunkType.ERROR,
                sequence_id=sequence_id,
                content=f"Event conversion error: {str(e)}",
                is_final=True,
                metadata={
                    "error_type": "event_conversion_error",
                    "original_event": str(adk_event) if adk_event else "None"
                }
            )
