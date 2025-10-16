# -*- coding: utf-8 -*-
"""ADK Domain Agent Implementation."""

import logging
from datetime import datetime
from typing import Any, Dict

from ...contracts import (
    AgentRequest,
    LiveExecutionResult,
    TaskResult,
    TaskStatus,
    UniversalMessage,
)
from ..base.domain_agent import DomainAgent
from .adk_agent_hooks import AdkAgentHooks
from .adk_event_converter import AdkEventConverter


class AdkDomainAgent(DomainAgent):
    """
    ADK-specific domain agent implementation.

    Wraps ADK agent functionality and provides integration with ADK's
    native memory, observability, and tool execution capabilities.
    """

    def __init__(
        self,
        agent_id: str,
        config: Dict[str, Any],
        runtime_context: Dict[str, Any] = None,
    ):
        """Initialize ADK domain agent with optional runtime context."""
        super().__init__(agent_id, config, runtime_context)
        self.logger = logging.getLogger(__name__)
        self.adk_agent = None
        self.hooks = AdkAgentHooks(self)
        self.event_converter = AdkEventConverter()
        self._tools_initialized = False  # Track if tools have been initialized

    # === Core Interface Methods ===

    async def initialize(self):
        """
        Initialize ADK domain agent.

        Creates the ADK agent instance needed for session context creation.
        """
        try:
            # Create ADK agent instance for session context
            await self._create_adk_agent()
            
            # Check if runtime context is available (post session context creation)
            runner = self.runtime_context.get("runner")
            session_service = self.runtime_context.get("session_service")

            if runner and session_service:
                # Runtime context available - agent is ready
                await self.hooks.on_agent_created()
                self._initialized = True
                return

            # If no runtime context yet, agent is still initialized 
            # (session context will be created by adapter)
            await self.hooks.on_agent_created()
            self._initialized = True

        except Exception as e:
            raise RuntimeError(f"Failed to initialize ADK agent: {str(e)}")
    
    async def _create_adk_agent(self, available_tools=None):
        """Create ADK agent instance for session execution within domain agent scope."""
        try:
            from google.adk import Agent
            
            # Get model configuration from user config or environment defaults
            model_identifier = self._get_model_configuration()
            
            # Use factory to create appropriate model instance
            from ...framework.adk.model_factory import AdkModelFactory
            model = AdkModelFactory.create_model(model_identifier, self._get_settings())
            
            # Get tools - either from parameter or default empty list
            if available_tools:
                tools = self._convert_universal_tools_to_adk(available_tools)
                self.logger.info(f"Creating ADK agent with {len(tools)} tools from available_tools")
            else:
                tools = []
                self.logger.info("Creating ADK agent with empty tool list")
            
            # Create the ADK agent with model configuration and tools
            self.adk_agent = Agent(
                name=self.config.get("name", self.agent_id),
                description=self.config.get("description", "ADK Domain Agent"),
                instruction=self.config.get("system_prompt", "You are a helpful AI assistant."),
                model=model,
                tools=tools,
            )
            
            self.logger.info(f"Created ADK agent: {self.adk_agent.name}")
            
        except ImportError as e:
            # ADK not available - set to None
            self.logger.warning(f"ADK not available: {str(e)}")
            self.adk_agent = None
        except Exception as e:
            # Log error but don't fail initialization
            self.logger.error(f"Failed to create ADK agent: {str(e)}")
            self.adk_agent = None

    def _get_model_configuration(self) -> str:
        """Get model configuration from user config or environment defaults."""
        # Priority: 1. User config, 2. Environment default model, 3. ADK default
        
        # Check if user specified a model in config
        if "model" in self.config and self.config["model"]:
            return self.config["model"]
        
        # Check if user specified model in model_config
        if "model_config" in self.config and isinstance(self.config["model_config"], dict):
            model_config = self.config["model_config"]
            if "model" in model_config and model_config["model"]:
                return model_config["model"]
        
        # Fall back to environment default model (LLM-agnostic)
        try:
            from ...config.settings import Settings
            settings = Settings()
            return settings.default_model
        except Exception:
            # ADK default - let ADK handle model selection
            return "gemini-1.5-flash"

    def _get_settings(self):
        """Get application settings for model factory."""
        try:
            from ...config.settings import Settings
            return Settings()
        except Exception:
            return None

    def _get_adk_tools(self, agent_request=None):
        """Get tools for ADK agent - focused on MCP tools from TaskRequest.
        
        Args:
            agent_request: Optional AgentRequest containing TaskRequest with available_tools
        """
        try:
            # Priority: Use MCP tools from TaskRequest.available_tools
            if agent_request and agent_request.task_request and agent_request.task_request.available_tools:
                self.logger.info(f"Using {len(agent_request.task_request.available_tools)} MCP tools from TaskRequest")
                return self._convert_universal_tools_to_adk(agent_request.task_request.available_tools)
            
            # Fallback: Return empty list - no legacy builtin tools needed
            self.logger.info("No MCP tools available from TaskRequest, using empty tool list")
            return []
            
        except Exception as e:
            # Simple error handling - return empty tools on failure
            self.logger.warning(f"Failed to configure ADK tools: {str(e)}")
            return []

    def _convert_universal_tools_to_adk(self, universal_tools):
        """Convert UniversalTool objects to ADK-compatible async functions.

        Args:
            universal_tools: List of UniversalTool objects from TaskRequest

        Returns:
            List of ADK-compatible async function objects
        """
        adk_tools = []

        try:
            tool_service = self.runtime_context.get("tool_service")
            if not tool_service:
                self.logger.warning(
                    "No tool service available for UniversalTool conversion"
                )
                return []

            for universal_tool in universal_tools:
                try:
                    # Create ADK-compatible async function with closure
                    def create_async_adk_wrapper(tool):
                        async def async_adk_tool(**kwargs):
                            """ADK native async tool function."""

                            # Create ToolRequest
                            from ...contracts import ToolRequest
                            tool_request = ToolRequest(
                                tool_name=(
                                    tool.name.split('.')[-1]
                                    if '.' in tool.name else tool.name
                                ),
                                tool_namespace=tool.namespace,
                                parameters=kwargs,
                                session_id=self.runtime_context.get(
                                    "session_id"
                                )
                            )

                            # Direct await - no asyncio.run or
                            # ThreadPoolExecutor needed!
                            result = await tool_service.execute_tool(
                                tool_request
                            )

                            # Simple result processing
                            if result and result.status.value == "success":
                                return {
                                    "status": "success",
                                    "result": result.result_data,
                                    "tool_name": tool.name,
                                    "namespace": tool.namespace,
                                    "execution_time": getattr(
                                        result, 'execution_time', 0
                                    )
                                }
                            else:
                                return {
                                    "status": "error",
                                    "error": (
                                        result.error_message if result
                                        else "Tool execution failed"
                                    ),
                                    "tool_name": tool.name
                                }

                        # Set function metadata for ADK
                        async_adk_tool.__name__ = (
                            tool.name.split('.')[-1]
                            if '.' in tool.name else tool.name
                        )
                        async_adk_tool.__doc__ = (
                            tool.description or f"Tool: {tool.name}"
                        )

                        # Add parameter annotations if available
                        if (tool.parameters_schema and
                                isinstance(tool.parameters_schema, dict)):
                            properties = tool.parameters_schema.get(
                                'properties', {}
                            )
                            annotations = {}
                            for param_name, param_info in properties.items():
                                param_type = param_info.get('type', 'str')
                                if param_type == 'string':
                                    annotations[param_name] = str
                                elif param_type == 'integer':
                                    annotations[param_name] = int
                                elif param_type == 'boolean':
                                    annotations[param_name] = bool
                                elif param_type == 'number':
                                    annotations[param_name] = float

                            if annotations:
                                async_adk_tool.__annotations__ = annotations

                        return async_adk_tool

                    # Use ADK's FunctionTool constructor for async functions
                    from google.adk.tools import FunctionTool
                    adk_function = FunctionTool(
                        func=create_async_adk_wrapper(universal_tool)
                    )
                    adk_tools.append(adk_function)
                    self.logger.debug(
                        f"Created async ADK function for {universal_tool.name}"
                    )

                except Exception as e:
                    self.logger.error(
                        f"Error converting tool {universal_tool.name}: {e}"
                    )
                    continue

            self.logger.info(
                f"Successfully converted {len(adk_tools)} UniversalTools "
                f"to async ADK functions"
            )
            return adk_tools

        except Exception as e:
            self.logger.error(f"Failed to convert UniversalTools to ADK: {e}")
            return []
    
    async def update_tools(self, available_tools):
        """
        Update agent tools dynamically.
        
        Args:
            available_tools: List of UniversalTool objects
        """
        if self.adk_agent and available_tools:
            tools = self._convert_universal_tools_to_adk(available_tools)
            self.adk_agent.tools = tools
            self._tools_initialized = True
            self.logger.info(f"Updated ADK agent with {len(tools)} tools")
        elif available_tools:
            # If agent doesn't exist, create it with tools
            await self._create_adk_agent(available_tools)
            self._tools_initialized = True
            self.logger.info(f"Created ADK agent with {len(available_tools)} tools")

    async def execute(self, agent_request: AgentRequest) -> TaskResult:
        """
        Execute task through ADK agent using runtime context.

        Args:
            agent_request: The agent request containing task details

        Returns:
            TaskResult: The result of task execution
        """
        try:
            start_time = datetime.now()

            # Pre-execution hooks
            await self.hooks.before_execution(agent_request)

            # Initialize tools only once or when tools change
            if not self._tools_initialized:
                if (agent_request.task_request and 
                    agent_request.task_request.available_tools):
                    
                    self.logger.info(f"Initializing ADK agent with {len(agent_request.task_request.available_tools)} tools")
                    await self._create_adk_agent(agent_request.task_request.available_tools)
                else:
                    # Mark as initialized even without tools - agent already exists from initialize()
                    self.logger.info("Marking tools as initialized (no tools specified)")
                
                self._tools_initialized = True

            # Execute through ADK using runtime context
            result = await self._execute_with_adk_runner(agent_request)

            # Post-execution hooks
            await self.hooks.after_execution(agent_request, result)

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            result.created_at = datetime.now()

            return result

        except Exception as e:
            error_result = TaskResult(
                task_id=agent_request.task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"ADK execution failed: {str(e)}",
                created_at=datetime.now(),
                metadata={"framework": "adk", "agent_id": self.agent_id},
            )

            # Error handling hooks
            await self.hooks.on_error(agent_request, e)

            return error_result

    async def execute_live(self, task_request) -> LiveExecutionResult:
        """
        Execute task in live/interactive mode using runtime context.

        Args:
            task_request: The task request to execute

        Returns:
            LiveExecutionResult: Tuple of (event_stream, communicator)
        """
        try:
            # Get runtime components provided by adapter
            runner = self.runtime_context.get("runner")
            session_id = self.runtime_context.get("session_id")
            user_id = self.runtime_context.get("user_id", "anonymous")

            if not runner or not session_id:
                return self._create_error_live_result(
                    task_request.task_id, "ADK runtime context not available for live execution"
                )

            # Create LiveRequestQueue in agent layer (ADK best practice)
            try:
                from google.adk.runners import LiveRequestQueue
                live_request_queue = LiveRequestQueue()
            except ImportError:
                return self._create_error_live_result(
                    task_request.task_id, "ADK LiveRequestQueue not available"
                )

            # Create live execution stream using real ADK streaming
            async def adk_live_stream():
                from ...contracts import TaskChunkType, TaskStreamChunk

                try:
                    # Convert messages to ADK format and send initial message
                    adk_content = self._convert_messages_to_adk_content(
                        task_request.messages
                    )
                    
                    # Send initial message to live request queue
                    await self._send_initial_message_to_live_queue(
                        live_request_queue, adk_content
                    )

                    # Stream real ADK live events
                    live_events = runner.run_live(
                        user_id=user_id,
                        session_id=session_id,
                        live_request_queue=live_request_queue
                    )

                    sequence_id = 0
                    async for adk_event in live_events:
                        # Use event converter to transform ADK events to TaskStreamChunk
                        chunk = self.event_converter.convert_adk_event_to_chunk(
                            adk_event, task_request.task_id, sequence_id
                        )
                        
                        if chunk is not None:
                            yield chunk
                            sequence_id += 1

                except Exception as e:
                    yield TaskStreamChunk(
                        task_id=task_request.task_id,
                        chunk_type=TaskChunkType.ERROR,
                        sequence_id=0,
                        content=f"ADK live execution failed: {str(e)}",
                        is_final=True,
                        metadata={"error_type": "execution_error", "framework": "adk"},
                    )

            # Use framework-level communicator with agent-created queue
            from ...framework.adk.live_communicator import AdkLiveCommunicator
            communicator = AdkLiveCommunicator(live_request_queue)
            
            return (adk_live_stream(), communicator)

        except Exception as e:
            return self._create_error_live_result(
                task_request.task_id, f"ADK live execution setup failed: {str(e)}"
            )

    async def get_state(self) -> Dict[str, Any]:
        """Get current agent state."""
        return {
            "agent_id": self.agent_id,
            "status": "ready" if self._initialized else "not_initialized",
            "config": self.config,
            "runtime_available": bool(self.runtime_context.get("runner")),
            "session_id": self.runtime_context.get("session_id"),
            "memory": {},  # TODO: Get from ADK context.state if needed
            "metrics": {},  # TODO: Get from ADK metrics if needed
        }

    async def cleanup(self):
        """Cleanup ADK agent resources."""
        try:
            # Runtime resources are managed by adapter
            # Agent just needs to cleanup its own state
            await self.hooks.on_agent_destroyed()
            self._initialized = False

        except Exception:
            # Log error but don't raise to avoid blocking cleanup
            pass

    # === ADK Execution Methods ===

    async def _send_initial_message_to_live_queue(
        self, live_request_queue, adk_content
    ):
        """Send initial message to ADK LiveRequestQueue."""
        try:
            # Import ADK types for content creation
            from google.genai import types

            # Handle different content types
            if isinstance(adk_content, str):
                # Text-only content
                content = types.Content(role="user", parts=[types.Part(text=adk_content)])
            elif hasattr(adk_content, 'role') and hasattr(adk_content, 'parts'):
                # Already ADK Content object
                content = adk_content
            else:
                # Fallback to string conversion
                content = types.Content(role="user", parts=[types.Part(text=str(adk_content))])

            # Send initial message to start conversation
            live_request_queue.send_content(content=content)

        except ImportError:
            # ADK not available - this is expected in some environments
            pass
        except Exception as e:
            raise RuntimeError(f"Failed to send initial message: {str(e)}")

    async def _execute_with_adk_runner(self, agent_request: AgentRequest) -> TaskResult:
        """
        Execute task using ADK Runner from runtime context with proper ADK agent creation.
        
        This method creates and manages ADK agent instances within the domain agent scope,
        ensuring proper hook integration and lifecycle management.

        Args:
            agent_request: The agent request containing task details

        Returns:
            TaskResult: The result of task execution
        """
        task_request = agent_request.task_request

        # Get runtime components provided by adapter
        runner = self.runtime_context.get("runner")
        user_id = self.runtime_context.get("user_id", "anonymous")
        
        # Use session_id from AgentRequest if available, fallback to runtime context
        session_id = agent_request.session_id or self.runtime_context.get("session_id")

        if not runner or not session_id:
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message="ADK runtime context not available",
                metadata={"framework": "adk", "agent_id": self.agent_id},
            )

        try:
            # Convert our message format to ADK format
            adk_content = self._convert_messages_to_adk_content(task_request.messages)

            # Execute using ADK Runner with proper ADK agent creation
            adk_response = await self._run_adk_with_runner_and_agent(
                runner, user_id, session_id, adk_content
            )

            # Convert ADK response back to our format
            return self._convert_adk_response_to_task_result(
                adk_response, task_request.task_id
            )

        except Exception as e:
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"ADK execution error: {str(e)}",
                metadata={"framework": "adk", "agent_id": self.agent_id},
            )

    async def _run_adk_with_runner_and_agent(
        self, runner, user_id: str, session_id: str, adk_content
    ):
        """
        Execute task through ADK Runner with proper ADK agent creation within domain scope.
        
        This method ensures that ADK agent creation happens within the domain agent,
        enabling proper hook integration and lifecycle management.
        """
        try:
            # Import ADK types for content creation
            from google.genai import types

            # Handle different content types for ADK
            if isinstance(adk_content, str):
                # Text-only content
                content = types.Content(role="user", parts=[types.Part(text=adk_content)])
            elif hasattr(adk_content, 'role') and hasattr(adk_content, 'parts'):
                # Already ADK Content object
                content = adk_content
            else:
                # Fallback to string conversion
                content = types.Content(role="user", parts=[types.Part(text=str(adk_content))])
            self.logger.debug(f"About to call runner.run_async with user_id: {user_id}, session_id: {session_id}")

            # Get the actual ADK session from runtime context
            adk_session = self.runtime_context.get("adk_session")
            if adk_session:
                # Use the actual ADK session ID if available
                actual_adk_session_id = getattr(adk_session, 'id', session_id)
            else:
                actual_adk_session_id = session_id

            # Check if we have an ADK agent created, if not create one
            if not self.adk_agent:
                self.logger.warning("No ADK agent found, creating one within domain scope")
                await self._create_adk_agent()
            
            # Execute through ADK Runner using the created agent context
            events = runner.run_async(
                user_id=user_id, 
                session_id=actual_adk_session_id, 
                new_message=content
            )

            # Process events to get final response with enhanced selection logic
            all_responses = []
            
            async for event in events:
                # Process all events with content
                if event.content:
                    # Extract text from parts
                    if hasattr(event.content, 'parts') and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                text = part.text.strip()
                                if text and len(text) > 10:  # Minimum content threshold
                                    all_responses.append({
                                        'text': text,
                                        'is_final': event.is_final_response(),
                                        'length': len(text)
                                    })
                    
                    # Extract text directly from content
                    if hasattr(event.content, 'text') and event.content.text:
                        text = event.content.text.strip()
                        if text and len(text) > 10:
                            all_responses.append({
                                'text': text,
                                'is_final': event.is_final_response(),
                                'length': len(text)
                            })
            
            # Select best response using general quality heuristics
            if all_responses:
                def score_response(resp):
                    text = resp['text']
                    score = 0
                    
                    # Length score - longer responses often more comprehensive
                    score += len(text) / 100
                    
                    # Content quality indicators
                    quality_indicators = [
                        '.',  # Proper sentences
                        '\n',  # Multi-line structure
                        ':',  # Explanatory content
                        '-',  # Lists or bullet points
                    ]
                    quality_score = sum(5 for indicator in quality_indicators 
                                      if text.count(indicator) > 0)
                    score += quality_score
                    
                    # Avoid obviously incomplete responses
                    incomplete_patterns = ['...', 'please wait', 'loading', 'error occurred']
                    incomplete_penalty = sum(20 for pattern in incomplete_patterns 
                                           if pattern.lower() in text.lower())
                    score -= incomplete_penalty
                    
                    # Prefer final responses slightly
                    if resp['is_final']:
                        score += 5
                    
                    return score
                
                best_response = max(all_responses, key=score_response)
                return best_response['text']
            else:
                return "No valid response received from ADK"

        except ImportError:
            # ADK not available, return mock response
            return f"Mock ADK processed: {adk_content}"
        except Exception as e:
            raise RuntimeError(f"ADK Runner execution failed: {str(e)}")

    # === Format Conversion Methods ===

    def _convert_messages_to_adk_content(self, messages: list):
        """
        Convert messages to ADK content format, supporting both text and multimodal content.
        
        Returns:
            For text-only: str content
            For multimodal: ADK Content object with parts
        """
        if not messages:
            return "Hello"

        # Check if any message contains multimodal content
        has_multimodal = False
        user_messages = []
        
        for msg in messages:
            if isinstance(msg, UniversalMessage):
                if msg.role == "user":
                    user_messages.append(msg)
                    # Check if this message has multimodal content
                    if isinstance(msg.content, list):
                        has_multimodal = True
            elif isinstance(msg, dict):
                if msg.get("role") == "user":
                    # Convert dict to UniversalMessage for consistency
                    universal_msg = UniversalMessage(
                        role=msg.get("role", "user"),
                        content=msg.get("content", "")
                    )
                    user_messages.append(universal_msg)

        if not user_messages:
            return "Hello"
        
        # If no multimodal content, return simple text format for backward compatibility
        if not has_multimodal:
            text_contents = []
            for msg in user_messages:
                if isinstance(msg.content, str):
                    text_contents.append(msg.content)
            return " ".join(text_contents) if text_contents else "Hello"
        
        # Handle multimodal content - return ADK Content object
        try:
            from google.genai import types
            
            # Convert all user messages to ADK parts format
            all_parts = []
            
            for msg in user_messages:
                adk_message = self.event_converter.convert_universal_message_to_adk(msg)
                if adk_message and "parts" in adk_message:
                    for part_dict in adk_message["parts"]:
                        if "text" in part_dict:
                            all_parts.append(types.Part(text=part_dict["text"]))
                        elif "inline_data" in part_dict:
                            # Create ADK Blob for image data
                            blob = types.Blob(
                                mime_type=part_dict["inline_data"]["mime_type"],
                                data=part_dict["inline_data"]["data"]
                            )
                            all_parts.append(types.Part(inline_data=blob))
            
            if all_parts:
                return types.Content(role="user", parts=all_parts)
            else:
                return "Hello"
                
        except ImportError as e:
            self.logger.warning(f"ADK types not available for multimodal content: {e}")
            # Fallback to text-only
            text_contents = []
            for msg in user_messages:
                if isinstance(msg.content, str):
                    text_contents.append(msg.content)
                elif isinstance(msg.content, list):
                    # Extract text parts only as fallback
                    for part in msg.content:
                        if hasattr(part, 'text') and part.text:
                            text_contents.append(part.text)
            return " ".join(text_contents) if text_contents else "Hello"
        except Exception as e:
            self.logger.error(f"Failed to convert multimodal content: {e}")
            return "Hello"

    def _convert_adk_response_to_task_result(
        self, adk_response, task_id: str
    ) -> TaskResult:
        """Convert ADK response to our TaskResult format."""
        try:
            # Create response message
            response_message = UniversalMessage(
                role="assistant",
                content=str(adk_response),
                metadata={"framework": "adk", "agent_id": self.agent_id},
            )

            return TaskResult(
                task_id=task_id,
                status=TaskStatus.SUCCESS,
                result_data={
                    "framework": "adk",
                    "agent_id": self.agent_id,
                    "response_length": len(str(adk_response)),
                    "processing_completed": True,
                },
                messages=[response_message],
                metadata={"framework": "adk", "agent_id": self.agent_id},
            )

        except Exception as e:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.ERROR,
                error_message=f"Failed to convert ADK response: {str(e)}",
                metadata={"framework": "adk", "agent_id": self.agent_id},
            )

    # === Live Execution Helpers ===

    def _create_error_live_result(self, task_id: str, error_message: str):
        """Create error live execution result."""
        
        async def error_stream():
            from ...contracts import TaskChunkType, TaskStreamChunk

            yield TaskStreamChunk(
                task_id=task_id,
                chunk_type=TaskChunkType.ERROR,
                sequence_id=0,
                content=error_message,
                is_final=True,
                metadata={"error_type": "runtime_error", "framework": "adk"},
            )

        # Use framework-level error communicator
        class ErrorCommunicator:
            def send_user_response(self, response):
                """Null implementation."""
                pass

            def send_user_message(self, message: str):
                """Null implementation."""
                pass

            def send_cancellation(self, reason: str):
                """Null implementation."""
                pass

            def close(self):
                pass

        return (error_stream(), ErrorCommunicator())

