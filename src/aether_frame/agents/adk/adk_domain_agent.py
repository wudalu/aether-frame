# -*- coding: utf-8 -*-
"""ADK Domain Agent Implementation."""

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
        self.adk_agent = None
        self.hooks = AdkAgentHooks(self)
        self.event_converter = AdkEventConverter()

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
    
    async def _create_adk_agent(self):
        """Create ADK agent instance for session execution."""
        try:
            from google.adk import Agent
            
            # Get model configuration from user config or environment defaults
            model_identifier = self._get_model_configuration()
            
            # Use factory to create appropriate model instance
            from ...framework.adk.model_factory import AdkModelFactory
            model = AdkModelFactory.create_model(model_identifier, self._get_settings())
            
            # Create the ADK agent with model configuration
            self.adk_agent = Agent(
                name=self.config.get("name", self.agent_id),
                description=self.config.get("description", "ADK Domain Agent"),
                instruction=self.config.get("system_prompt", "You are a helpful AI assistant."),
                model=model,
            )
            
        except ImportError as e:
            # ADK not available - set to None
            self.adk_agent = None
        except Exception as e:
            # Log error but don't fail initialization
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
        self, live_request_queue, adk_content: str
    ):
        """Send initial message to ADK LiveRequestQueue."""
        try:
            # Import ADK types for content creation
            from google.genai import types

            # Create ADK content for initial message
            content = types.Content(role="user", parts=[types.Part(text=adk_content)])

            # Send initial message to start conversation
            live_request_queue.send_content(content=content)

        except ImportError:
            # ADK not available - this is expected in some environments
            pass
        except Exception as e:
            raise RuntimeError(f"Failed to send initial message: {str(e)}")

    async def _execute_with_adk_runner(self, agent_request: AgentRequest) -> TaskResult:
        """
        Execute task using ADK Runner from runtime context.

        Args:
            agent_request: The agent request containing task details

        Returns:
            TaskResult: The result of task execution
        """
        task_request = agent_request.task_request

        # Get runtime components provided by adapter
        runner = self.runtime_context.get("runner")
        user_id = self.runtime_context.get("user_id", "anonymous")
        session_id = self.runtime_context.get("session_id")

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

            # Execute using ADK Runner from runtime context
            adk_response = await self._run_adk_with_runner(
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

    async def _run_adk_with_runner(
        self, runner, user_id: str, session_id: str, adk_content
    ):
        """Execute task through ADK Runner."""
        try:
            # Import ADK types for content creation
            from google.genai import types

            # Create ADK content
            content = types.Content(role="user", parts=[types.Part(text=adk_content)])

            # Run through ADK Runner using async method
            events = runner.run_async(
                user_id=user_id, session_id=session_id, new_message=content
            )

            # Process events to get final response
            final_response = None
            async for event in events:
                if event.is_final_response() and event.content:
                    final_response = event.content.parts[0].text.strip()
                    break

            return final_response or "No response from ADK"

        except ImportError:
            # ADK not available, return mock response
            return f"Mock ADK processed: {adk_content}"
        except Exception as e:
            raise RuntimeError(f"ADK Runner execution failed: {str(e)}")

    # === Format Conversion Methods ===

    def _convert_messages_to_adk_content(self, messages: list) -> str:
        """Convert our messages to ADK content format."""
        if not messages:
            return "Hello"

        # Extract user messages and combine them
        user_messages = []
        for msg in messages:
            if isinstance(msg, UniversalMessage):
                if msg.role == "user":
                    user_messages.append(msg.content)
            elif isinstance(msg, dict):
                if msg.get("role") == "user":
                    user_messages.append(msg.get("content", ""))

        return " ".join(user_messages) if user_messages else "Hello"

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
                result_data={"response": response_message.content},
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

