# -*- coding: utf-8 -*-
"""ADK Domain Agent Implementation."""

import inspect
import logging
try:
    from contextlib import aclosing
except ImportError:  # Python <3.10 compatibility
    class _AsyncClosing:
        def __init__(self, resource):
            self._resource = resource

        async def __aenter__(self):
            return self._resource

        async def __aexit__(self, exc_type, exc, tb):
            aclose = getattr(self._resource, "aclose", None)
            if callable(aclose):
                await aclose()

    def aclosing(resource):
        return _AsyncClosing(resource)
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...contracts import (
    AgentRequest,
    ErrorCode,
    LiveExecutionResult,
    TaskResult,
    TaskStatus,
    UniversalMessage,
    build_error,
)
from ..base.domain_agent import DomainAgent
from .adk_agent_hooks import AdkAgentHooks
from .adk_event_converter import AdkEventConverter
from .tool_conversion import build_adk_agent, create_function_tools


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
        self._active_task_request = None  # Track current TaskRequest context
        self._tool_approval_policy: Dict[str, bool] = {}

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
        model_identifier = self._get_model_configuration()
        raw_model_config = self.config.get("model_config") if isinstance(self.config, dict) else None
        model_config = deepcopy(raw_model_config) if raw_model_config else {}
        raw_framework_config = (
            self.config.get("framework_config") if isinstance(self.config, dict) else None
        )
        framework_config = deepcopy(raw_framework_config) if raw_framework_config else {}

        if model_config:
            def _shorten_tool_names(payload):
                if isinstance(payload, dict):
                    return {
                        key: (_shorten_tool_names(value) if key != "name" else _shorten_name(value))
                        for key, value in payload.items()
                    }
                if isinstance(payload, list):
                    return [_shorten_tool_names(item) for item in payload]
                return payload

            def _shorten_name(value):
                if isinstance(value, str) and "." in value:
                    return value.split(".")[-1]
                return value

            tool_choice = model_config.get("tool_choice")
            if isinstance(tool_choice, dict):
                model_config["tool_choice"] = _shorten_tool_names(tool_choice)
            elif isinstance(tool_choice, str):
                model_config["tool_choice"] = _shorten_name(tool_choice)

        tool_service = self.runtime_context.get("tool_service")
        settings = self._get_settings()

        self.adk_agent = build_adk_agent(
            name=self.config.get("name", self.agent_id),
            description=self.config.get("description", "ADK Domain Agent"),
            instruction=self.config.get("system_prompt", "You are a helpful AI assistant."),
            model_identifier=model_identifier,
            tool_service=tool_service,
            universal_tools=available_tools,
            request_factory=self._prepare_tool_request,
            settings=settings,
            enable_streaming=True,
            model_config=model_config,
            framework_config=framework_config,
        )

        if self.adk_agent:
            self.logger.info(f"Created ADK agent: {self.adk_agent.name}")
        else:
            raise RuntimeError("Failed to create ADK agent - missing dependencies or configuration")

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
        tool_service = self._lookup_runtime_value("tool_service")
        tool_list = list(universal_tools)
        self._tool_approval_policy = {}
        for tool in tool_list:
            metadata = getattr(tool, "metadata", {}) or {}
            requires = metadata.get("requires_approval")
            self._tool_approval_policy[tool.name] = bool(requires) if requires is not None else True
            if "." in tool.name:
                short_name = tool.name.split(".")[-1]
                self._tool_approval_policy.setdefault(short_name, self._tool_approval_policy[tool.name])

        self._store_runtime_value("tool_approval_policy", dict(self._tool_approval_policy))

        tools = create_function_tools(
            tool_service,
            tool_list,
            request_factory=self._prepare_tool_request,
            approval_callback=self._await_tool_approval,
        )
        self.logger.info(
            "Successfully converted %d UniversalTools to async ADK functions",
            len(tools),
        )
        return tools

    async def _await_tool_approval(self, tool, parameters: Dict[str, Any]):
        broker = self._lookup_runtime_value("approval_broker")
        requires = self._tool_approval_policy.get(tool.name, True)
        if requires is None and "." in tool.name:
            requires = self._tool_approval_policy.get(tool.name.split(".")[-1], True)
        if not requires:
            return {"approved": True, "requires_approval": False}
        if not broker:
            return {"approved": True}
        try:
            return await broker.wait_for_tool_approval(tool.name, parameters)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Tool approval check failed for %s: %s", tool.name, exc)
            return {"approved": False, "error": str(exc)}

    def _lookup_runtime_value(self, key: str):
        context = self.runtime_context
        if isinstance(context, dict):
            return context.get(key) or context.get("metadata", {}).get(key)
        metadata = getattr(context, "metadata", {})
        if key in metadata:
            return metadata[key]
        return getattr(context, key, None)

    def _store_runtime_value(self, key: str, value) -> None:
        context = self.runtime_context
        if isinstance(context, dict):
            context.setdefault("metadata", {})[key] = value
        else:
            metadata = getattr(context, "metadata", None)
            if metadata is not None:
                metadata[key] = value
            else:
                setattr(context, key, value)

    def _prepare_tool_request(self, tool, parameters: Dict[str, Any]):
        """Build ToolRequest populated with contextual metadata for MCP tooling."""
        from ...contracts import ToolRequest

        task_request = self._active_task_request

        user_context = getattr(task_request, "user_context", None) if task_request else None
        session_context = getattr(task_request, "session_context", None) if task_request else None
        execution_context = getattr(task_request, "execution_context", None) if task_request else None

        metadata: Dict[str, Any] = {}
        if task_request and getattr(task_request, "metadata", None):
            metadata.update(deepcopy(task_request.metadata))

        tool_metadata = getattr(tool, "metadata", None)
        if tool_metadata:
            metadata.setdefault("tool_metadata", deepcopy(tool_metadata))
            if isinstance(tool_metadata, dict) and "mcp_headers" in tool_metadata:
                base_headers = metadata.get("mcp_headers", {}).copy()
                tool_headers = deepcopy(tool_metadata["mcp_headers"])
                base_headers.update(tool_headers)
                metadata["mcp_headers"] = base_headers

        session_id = None
        if isinstance(self.runtime_context, dict):
            session_id = self.runtime_context.get("session_id")
        if not session_id and session_context:
            session_id = session_context.session_id
        if not session_id and task_request:
            session_id = task_request.session_id

        return ToolRequest(
            tool_name=(
                tool.name.split('.')[-1]
                if '.' in tool.name else tool.name
            ),
            tool_namespace=tool.namespace,
            parameters=parameters,
            session_id=session_id,
            user_context=user_context,
            session_context=session_context,
            execution_context=execution_context,
            metadata=metadata,
        )
    
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
        previous_task_request = self._active_task_request
        self._active_task_request = agent_request.task_request

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
            error_type = type(e).__name__
            error_message = f"ADK domain agent execution failed ({error_type}): {str(e)}"
            self.logger.error(
                f"ADK domain agent execution failed - agent_id: {self.agent_id}, error: {error_message}"
            )
            error_payload = build_error(
                ErrorCode.FRAMEWORK_EXECUTION,
                error_message,
                source="adk_domain_agent.execute",
                details={"agent_id": self.agent_id, "error_type": error_type},
            )
            error_result = TaskResult(
                task_id=agent_request.task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=error_message,
                error=error_payload,
                created_at=datetime.now(),
                session_id=agent_request.session_id or self.runtime_context.get("session_id"),
                metadata={
                    "framework": "adk",
                    "agent_id": self.agent_id,
                    "error_stage": "adk_domain_agent.execute",
                    "error_type": error_type,
                },
            )

            # Error handling hooks
            await self.hooks.on_error(agent_request, e)

            return error_result
        finally:
            self._active_task_request = previous_task_request

    async def execute_live(self, task_request) -> LiveExecutionResult:
        """
        Execute task in live/interactive mode using runtime context.

        Args:
            task_request: The task request to execute

        Returns:
            LiveExecutionResult: Tuple of (event_stream, communicator)
        """
        previous_task_request = self._active_task_request
        self._active_task_request = task_request

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
                    async with aclosing(live_events) as adk_events:
                        async for adk_event in adk_events:
                            chunks = self.event_converter.convert_adk_event_to_chunk(
                                adk_event, task_request.task_id, sequence_id
                            )

                            if not chunks:
                                continue

                            for chunk in chunks:
                                chunk.sequence_id = sequence_id
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
                finally:
                    live_request_queue.close()

            # Use framework-level communicator with agent-created queue
            from ...framework.adk.live_communicator import AdkLiveCommunicator
            communicator = AdkLiveCommunicator(live_request_queue)
            
            return (adk_live_stream(), communicator)

        except Exception as e:
            return self._create_error_live_result(
                task_request.task_id, f"ADK live execution setup failed: {str(e)}"
            )
        finally:
            self._active_task_request = previous_task_request

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
            missing_parts = []
            if not runner:
                missing_parts.append("runner")
            if not session_id:
                missing_parts.append("session_id")
            detail = ", ".join(missing_parts) if missing_parts else "runtime context"
            error_message = f"ADK runtime context not available ({detail} missing)"
            self.logger.error(
                f"ADK runtime context missing - agent_id: {self.agent_id}, missing: {missing_parts or ['unknown']}"
            )
            error_payload = build_error(
                ErrorCode.FRAMEWORK_EXECUTION,
                error_message,
                source="adk_domain_agent.runtime_context",
                details={"agent_id": self.agent_id, "missing_components": missing_parts},
            )
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=error_message,
                error=error_payload,
                session_id=session_id,
                metadata={
                    "framework": "adk",
                    "agent_id": self.agent_id,
                    "error_stage": "adk_domain_agent.runtime_context",
                    "missing_components": missing_parts,
                },
            )

        try:
            messages_for_execution = list(task_request.messages or [])
            latest_query = self._extract_user_query(task_request.messages)
            memory_snippets = await self._retrieve_memory_snippets(
                latest_query, session_id=session_id
            )
            if memory_snippets:
                knowledge_message = "\n\n".join(memory_snippets)
                messages_for_execution.append(
                    UniversalMessage(
                        role="user",
                        content=f"[Retrieved Knowledge]\n{knowledge_message}",
                        metadata={
                            "source": "memory_service",
                            "snippet_count": len(memory_snippets),
                        },
                    )
                )
                self.logger.debug(
                    "Appended %d memory snippets to conversation for session %s",
                    len(memory_snippets),
                    session_id,
                )

            # Convert our message format to ADK format
            adk_content = self._convert_messages_to_adk_content(messages_for_execution)

            # Execute using ADK Runner with proper ADK agent creation
            adk_response = await self._run_adk_with_runner_and_agent(
                runner, user_id, session_id, adk_content
            )

            # Convert ADK response back to our format
            return self._convert_adk_response_to_task_result(
                adk_response, task_request.task_id
            )

        except Exception as e:
            error_type = type(e).__name__
            error_message = f"ADK runner execution failed ({error_type}): {str(e)}"
            self.logger.error(
                f"ADK runner execution failed - agent_id: {self.agent_id}, session_id: {session_id}, error: {error_message}"
            )
            error_payload = build_error(
                ErrorCode.FRAMEWORK_EXECUTION,
                error_message,
                source="adk_domain_agent.runner_execution",
                details={"agent_id": self.agent_id, "session_id": session_id, "error_type": error_type},
            )
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=error_message,
                error=error_payload,
                session_id=session_id,
                metadata={
                    "framework": "adk",
                    "agent_id": self.agent_id,
                    "error_stage": "adk_domain_agent.runner_execution",
                    "error_type": error_type,
                },
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

    def _extract_user_query(
        self, messages: Optional[List[UniversalMessage]]
    ) -> Optional[str]:
        """Get the latest user-authored text content to use as a memory query."""
        if not messages:
            return None

        for message in reversed(messages):
            if isinstance(message, UniversalMessage) and message.role == "user":
                if isinstance(message.content, str):
                    return message.content
            elif isinstance(message, dict) and message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, str):
                    return content
        return None

    async def _retrieve_memory_snippets(
        self, query: Optional[str], session_id: str
    ) -> List[str]:
        """Retrieve knowledge snippets from the runner memory service."""
        if not query:
            return []

        runner_context = self.runtime_context.get("runner_context") or {}
        memory_service = runner_context.get("memory_service")
        if not memory_service:
            return []

        app_name = runner_context.get("app_name") or self.runtime_context.get("app_name") or "aether-frame"
        user_id = (
            runner_context.get("session_user_ids", {}).get(session_id)
            or self.runtime_context.get("user_id")
            or "anonymous"
        )

        try:
            try:
                search_call = memory_service.search_memory(  # type: ignore[attr-defined]
                    app_name=app_name,
                    user_id=user_id,
                    query=query,
                )
            except TypeError:
                search_call = memory_service.search_memory(app_name, user_id, query)

            search_results = await search_call if inspect.isawaitable(search_call) else search_call
        except Exception as exc:
            self.logger.debug(
                "Memory search failed for session %s: %s", session_id, exc
            )
            return []

        entries = getattr(search_results, "results", None) or getattr(search_results, "entries", None)
        if not entries:
            return []

        snippets: List[str] = []
        for entry in entries:
            text = getattr(entry, "text", None) or getattr(entry, "content", None)
            if not text:
                continue
            text_value = str(text).strip()
            if text_value:
                snippets.append(text_value)
            if len(snippets) >= 3:
                break

        return snippets

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
            error_message = f"Failed to convert ADK response: {str(e)}"
            error_payload = build_error(
                ErrorCode.FRAMEWORK_EXECUTION,
                error_message,
                source="adk_domain_agent.convert_response",
                details={"agent_id": self.agent_id},
            )
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.ERROR,
                error_message=error_message,
                error=error_payload,
                metadata={"framework": "adk", "agent_id": self.agent_id},
            )

    # === Live Execution Helpers ===

    def _create_error_live_result(self, task_id: str, error_message: str):
        """Create error live execution result."""

        error_payload = build_error(
            ErrorCode.FRAMEWORK_EXECUTION,
            error_message,
            source="adk_domain_agent.live",
            details={"agent_id": self.agent_id},
        )

        async def error_stream():
            from ...contracts import TaskChunkType, TaskStreamChunk

            yield TaskStreamChunk(
                task_id=task_id,
                chunk_type=TaskChunkType.ERROR,
                sequence_id=0,
                content=error_payload.to_dict(),
                is_final=True,
                metadata={"error_type": "runtime_error", "framework": "adk", "stage": "error"},
                chunk_kind="error",
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
