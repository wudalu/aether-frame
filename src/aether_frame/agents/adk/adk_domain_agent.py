# -*- coding: utf-8 -*-
"""ADK Domain Agent Implementation."""

from datetime import datetime
from typing import Any, Dict, Optional

from ...contracts import AgentRequest, TaskResult, TaskStatus, UniversalMessage
from ..base.domain_agent import DomainAgent
from .adk_agent_hooks import AdkAgentHooks


class AdkDomainAgent(DomainAgent):
    """
    ADK-specific domain agent implementation.

    Wraps ADK agent functionality and provides integration with ADK's
    native memory, observability, and tool execution capabilities.
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """Initialize ADK domain agent."""
        super().__init__(agent_id, config)
        # FIXME: Use factory pattern for agent creation instead of direct framework check
        # See CLAUDE.md - AgentManager should use registered factories, not if/elif framework selection
        self.adk_agent = None
        self.hooks = AdkAgentHooks(self)

    async def initialize(self):
        """Initialize ADK agent instance using real ADK API."""
        try:
            # Import ADK modules (will be available after installation)
            # For now, we'll use try-catch to gracefully handle missing dependencies
            try:
                from google.adk.agents import Agent, LlmAgent

                # Determine agent type based on configuration
                agent_type = self.config.get("agent_type", "conversational_agent")
                model = self.config.get("model_config", {}).get(
                    "model", "gemini-2.0-flash"
                )

                # Create minimal ADK agent without tools
                system_instruction = self.config.get(
                    "system_prompt", "You are a helpful assistant."
                )

                # Create simple ADK agent based on type
                if agent_type in ["conversational_agent", "general_agent"]:
                    self.adk_agent = Agent(
                        name=self.agent_id, model=model, instruction=system_instruction
                    )
                else:
                    # Use LlmAgent for other types
                    self.adk_agent = LlmAgent(
                        name=self.agent_id, model=model, instruction=system_instruction
                    )

                # Apply ADK-specific hooks
                await self.hooks.on_agent_created()
                self._initialized = True

            except ImportError as import_err:
                # ADK not installed - use mock implementation
                self.adk_agent = None
                await self.hooks.on_agent_created()
                self._initialized = True

        except Exception as e:
            raise RuntimeError(f"Failed to initialize ADK agent: {str(e)}")

    async def execute(self, agent_request: AgentRequest) -> TaskResult:
        """
        Execute task through ADK agent.

        Args:
            agent_request: The agent request containing task details

        Returns:
            TaskResult: The result of task execution
        """
        if not self._initialized:
            return TaskResult(
                task_id=agent_request.task_request.task_id,
                status=TaskStatus.ERROR,
                error_message="ADK agent not initialized",
            )

        try:
            start_time = datetime.now()

            # Pre-execution hooks
            await self.hooks.before_execution(agent_request)

            # Execute through ADK
            result = await self._execute_adk_task(agent_request)

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
            )

            # Error handling hooks
            await self.hooks.on_error(agent_request, e)

            return error_result

    async def _execute_adk_task(self, agent_request: AgentRequest) -> TaskResult:
        """Execute task using ADK native functionality."""
        task_request = agent_request.task_request

        if self.adk_agent:
            # Use real ADK agent
            try:
                # Convert our messages to ADK format
                adk_input = self._convert_messages_for_adk(task_request.messages)

                # Execute through ADK agent using standard chat interface
                # ADK agents use chat() method for conversation
                result = self.adk_agent.chat(adk_input)

                # Convert ADK result back to our format
                return self._convert_adk_result_to_task_result(
                    result, task_request.task_id
                )

            except Exception as e:
                # If ADK execution fails, return error
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message=f"ADK execution error: {str(e)}",
                    metadata={"framework": "adk", "agent_id": self.agent_id},
                )
        else:
            # Use mock implementation when ADK is not available
            return self._mock_adk_execution(task_request)

    def _convert_messages_for_adk(self, messages: list) -> str:
        """Convert our messages to ADK input format."""
        if not messages:
            return "Hello"

        # For ADK, we typically need a single string input
        # Combine all user messages into one input
        user_messages = []
        for msg in messages:
            if isinstance(msg, UniversalMessage):
                if msg.role == "user":
                    user_messages.append(msg.content)
            elif isinstance(msg, dict):
                if msg.get("role") == "user":
                    user_messages.append(msg.get("content", ""))

        return " ".join(user_messages) if user_messages else "Hello"

    def _convert_adk_result_to_task_result(
        self, adk_result, task_id: str
    ) -> TaskResult:
        """Convert ADK result to our TaskResult format."""
        try:
            # ADK results can be in various formats
            if isinstance(adk_result, str):
                # Simple string result
                response_message = UniversalMessage(
                    role="assistant",
                    content=adk_result,
                    metadata={"framework": "adk", "agent_id": self.agent_id},
                )
            elif isinstance(adk_result, dict):
                # Structured result
                content = adk_result.get("content", str(adk_result))
                response_message = UniversalMessage(
                    role="assistant",
                    content=content,
                    metadata={
                        "framework": "adk",
                        "agent_id": self.agent_id,
                        "adk_result": adk_result,
                    },
                )
            else:
                # Unknown format, convert to string
                response_message = UniversalMessage(
                    role="assistant",
                    content=str(adk_result),
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
                error_message=f"Failed to convert ADK result: {str(e)}",
                metadata={"framework": "adk", "agent_id": self.agent_id},
            )

    def _mock_adk_execution(self, task_request) -> TaskResult:
        """Mock ADK execution when ADK is not available."""
        mock_message = UniversalMessage(
            role="assistant",
            content=f"Mock ADK processed task: {task_request.description}",
            metadata={"framework": "adk", "agent_id": self.agent_id, "mock": True},
        )

        return TaskResult(
            task_id=task_request.task_id,
            status=TaskStatus.SUCCESS,
            result_data={"response": mock_message.content},
            messages=[mock_message],
            metadata={"framework": "adk", "agent_id": self.agent_id, "mock": True},
        )

    def _get_adk_tools(self) -> list:
        """Convert our tools to ADK format."""
        # Return empty list - no tool calling for minimal implementation
        return []

    def _convert_to_adk_format(self, messages: list) -> list:
        """Convert universal messages to ADK format."""
        adk_messages = []
        for msg in messages:
            if isinstance(msg, UniversalMessage):
                # Use the built-in conversion method
                adk_messages.append(msg.to_adk_format())
            elif isinstance(msg, dict):
                # Handle legacy dict format
                adk_msg = {
                    "author": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "metadata": msg.get("metadata", {}),
                }
                adk_messages.append(adk_msg)
        return adk_messages

    def _build_adk_config(self) -> Dict[str, Any]:
        """Build ADK-specific configuration."""
        return {
            "agent_type": self.config.get("agent_type", "conversational"),
            "model_config": self.config.get("model_config", {}),
            "capabilities": self.config.get("capabilities", []),
            "memory_config": self.config.get("memory_config", {}),
            "tool_permissions": self.config.get("tool_permissions", []),
        }

    async def get_state(self) -> Dict[str, Any]:
        """Get current agent state."""
        # TODO: Get actual ADK agent state
        return {
            "agent_id": self.agent_id,
            "status": "ready" if self._initialized else "not_initialized",
            "config": self.config,
            "memory": {},  # TODO: Get from ADK context.state
            "metrics": {},  # TODO: Get from ADK metrics
        }

    async def cleanup(self):
        """Cleanup ADK agent resources."""
        try:
            if self.adk_agent:
                # TODO: Cleanup ADK agent
                # await self.adk_agent.shutdown()
                pass

            await self.hooks.on_agent_destroyed()
            self._initialized = False

        except Exception as e:
            # Log error but don't raise to avoid blocking cleanup
            pass
