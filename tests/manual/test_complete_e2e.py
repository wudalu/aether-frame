#!/usr/bin/env python3
"""
Complete End-to-End Test with Detailed Logging
This script performs comprehensive testing with full request/response logging.
"""

import asyncio
import logging
import sys
import os
import json
import warnings
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

# Load test environment
from dotenv import load_dotenv
load_dotenv(".env.test")

from aether_frame.bootstrap import create_ai_assistant, health_check_system, create_system_components
from aether_frame.config.settings import Settings
from aether_frame.contracts import (
    TaskRequest,
    UniversalMessage,
    TaskStatus,
    AgentConfig,
    ContentPart,
    ImageReference,
    UserContext,
    FrameworkType,
)


class CompleteE2ETestSuite:
    """
    Complete End-to-End test suite with detailed request/response logging.
    Supports multiple AI models: DeepSeek, GPT-4o, GPT-4.1
    """

    def __init__(self, test_name: str = "complete_e2e_test", models: List[str] = None, run_all_models: bool = False):
        """Initialize complete E2E test suite.
        
        Args:
            test_name: Name of the test suite
            models: List of specific models to test
            run_all_models: Whether to run tests on all supported models
        """
        self.test_name = test_name
        self.start_time = datetime.now()
        self.test_results: List[Dict[str, Any]] = []
        
        # Model configuration
        self.supported_models = {
            "deepseek-chat": {
                "provider": "deepseek",
                "api_key_env": "DEEPSEEK_API_KEY",
                "base_url": "https://api.deepseek.com/v1"
            },
            "qwen-vl-plus": {
                "provider": "dashscope",
                "api_key_env": "QWEN_API_KEY",
                "base_url": "QWEN_BASE_URL"
            },
            "dashscope/qwen-vl-plus": {
                "provider": "dashscope",
                "api_key_env": "QWEN_API_KEY",
                "base_url": "QWEN_BASE_URL"
            },
            "gpt-4o": {
                "provider": "openai",
                "api_key_env": "OPENAI_API_KEY",
                "base_url": "https://api.openai.com/v1"
            },
            "gpt-4.1": {
                "provider": "openai", 
                "api_key_env": "OPENAI_API_KEY",
                "base_url": "https://api.openai.com/v1"
            },
            "azure/gpt-4": {
                "provider": "azure_openai",
                "api_key_env": "AZURE_API_KEY",
                "base_url": "AZURE_API_BASE"
            },
            "azure/gpt-4o": {
                "provider": "azure_openai",
                "api_key_env": "AZURE_API_KEY",
                "base_url": "AZURE_API_BASE"
            },
            "azure-gpt-4": {
                "provider": "azure_openai",
                "api_key_env": "AZURE_API_KEY",
                "base_url": "AZURE_API_BASE"
            }
        }
        
        # Determine which models to test
        if run_all_models:
            self.test_models = list(self.supported_models.keys())
        elif models:
            self.test_models = [m for m in models if m in self.supported_models]
            if not self.test_models:
                raise ValueError(f"No valid models specified. Supported: {list(self.supported_models.keys())}")
        else:
            # Default to DeepSeek if no specific models requested
            self.test_models = ["deepseek-chat"]
        
        # Setup logging
        self.setup_logging()
        
        # Test configuration
        self.settings = Settings()
        self.assistant = None
        self.test_user_context = UserContext(user_id="complete_e2e_user")
        
        # Performance tracking
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "tool_calls_detected": 0,
            "total_execution_time": 0.0,
            "average_response_time": 0.0,
            "models_tested": [],
            "model_results": {},
        }

    def _build_user_context(self) -> UserContext:
        """Return default user context for requests."""
        return self.test_user_context

    def _summarize_message_content(self, content) -> str:
        """Create a short preview for logging."""
        if isinstance(content, str):
            return content[:100] + ("..." if len(content) > 100 else "")
        if isinstance(content, list):
            part_summaries = []
            for part in content:
                if isinstance(part, ContentPart):
                    if part.text:
                        summary = part.text[:30] + ("..." if len(part.text) > 30 else "")
                        part_summaries.append(f"text:{summary}")
                    elif part.image_reference:
                        part_summaries.append("image:base64")
                    elif part.function_call:
                        part_summaries.append(f"function:{part.function_call.tool_name}")
                    else:
                        part_summaries.append("content-part")
                else:
                    part_summaries.append(str(part))
            return " | ".join(part_summaries)
        return str(content)

    async def _create_agent_and_session(
        self,
        *,
        model_name: str,
        agent_type: str,
        system_prompt: str,
        initial_message: Optional[UniversalMessage],
        creation_task: str,
        creation_description: str,
        creation_metadata: Dict[str, Any],
        user_context: UserContext,
        model_config: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """Create an agent and obtain business chat session id."""
        creation_metadata = dict(creation_metadata or {})
        metadata = {
            "test_framework": "adk_complete_e2e",
            "framework_type": "adk",
            "test_suite": "complete_e2e",
            "preferred_model": model_name,
            "timestamp": datetime.now().isoformat(),
            "phase": "creation",
        }
        metadata.update(creation_metadata)

        business_chat_session_id = metadata.get("chat_session_id") or f"chat_session_{uuid4().hex[:12]}"
        metadata.setdefault("chat_session_id", business_chat_session_id)

        resolved_model_config = model_config.copy() if model_config else {
            "model": model_name,
            "temperature": 0.6,
            "max_tokens": 1500,
        }
        resolved_model_config["model"] = model_name

        creation_request = TaskRequest(
            task_id=creation_task,
            task_type="chat",
            description=creation_description,
            messages=[initial_message] if initial_message else [],
            agent_config=AgentConfig(
                agent_type=agent_type,
                system_prompt=system_prompt,
                model_config=resolved_model_config,
                available_tools=available_tools or [],
                framework_config={
                    "provider": "deepseek" if "deepseek" in model_name else "openai"
                },
            ),
            user_context=user_context,
            session_id=business_chat_session_id,
            metadata=metadata,
        )

        self.log_request_details(creation_request, f"{agent_type}_creation", model_name)
        creation_result = await self.assistant.process_request(creation_request)
        self.log_response_details(creation_result, f"{agent_type}_creation", 0.0, model_name)

        if creation_result.status != TaskStatus.SUCCESS:
            raise RuntimeError(
                f"Agent creation failed: {creation_result.error_message or 'unknown error'}"
            )

        agent_id = creation_result.agent_id
        if not agent_id:
            raise RuntimeError("Agent creation response missing agent_id")

        self.logger.info(
            f"Agent created successfully - agent_id={agent_id}, chat_session_id={business_chat_session_id}"
        )
        return agent_id, business_chat_session_id

    async def _run_conversation_test(
        self,
        *,
        test_case: str,
        model_name: str,
        agent_type: str,
        system_prompt: str,
        messages: List[UniversalMessage],
        creation_metadata: Optional[Dict[str, Any]] = None,
        conversation_metadata: Optional[Dict[str, Any]] = None,
        model_config: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[str]] = None,
        evaluate_response=None,
    ) -> bool:
        """Create agent lazily and execute a conversation test."""
        start_time = datetime.now()
        user_context = self._build_user_context()
        creation_metadata = dict(creation_metadata or {})
        conversation_metadata = dict(conversation_metadata or {})
        messages = messages or []

        initial_message = messages[0] if messages else None

        business_chat_session_id = (
            conversation_metadata.get("chat_session_id")
            or creation_metadata.get("chat_session_id")
            or f"chat_session_{uuid4().hex[:12]}"
        )
        creation_metadata.setdefault("chat_session_id", business_chat_session_id)
        conversation_metadata.setdefault("chat_session_id", business_chat_session_id)

        agent_id, _ = await self._create_agent_and_session(
            model_name=model_name,
            agent_type=agent_type,
            system_prompt=system_prompt,
            initial_message=initial_message,
            creation_task=f"e2e_create_{test_case}_{int(start_time.timestamp())}",
            creation_description=f"{test_case} agent creation",
            creation_metadata=creation_metadata,
            user_context=user_context,
            model_config=model_config,
            available_tools=available_tools,
        )

        conversation_request = TaskRequest(
            task_id=f"e2e_conversation_{test_case}_{int(datetime.now().timestamp())}",
            task_type="chat",
            description=f"{test_case} conversation",
            messages=messages,
            agent_id=agent_id,
            session_id=business_chat_session_id,
            user_context=user_context,
            metadata={
                "test_framework": "adk_complete_e2e",
                "framework_type": "adk",
                "test_suite": "complete_e2e",
                "test_case": test_case,
                "preferred_model": model_name,
                "timestamp": datetime.now().isoformat(),
                "phase": "conversation",
                **conversation_metadata,
            },
        )

        self.log_request_details(conversation_request, test_case, model_name)

        try:
            result = await self.assistant.process_request(conversation_request)
            execution_time = (datetime.now() - start_time).total_seconds()

            self.log_response_details(result, test_case, execution_time, model_name)

            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time

            if result.status == TaskStatus.SUCCESS and result.messages:
                passed = True
                extra_fields: Dict[str, Any] = {}
                warning_message: Optional[str] = None

                response_text = result.messages[0].content
                extra_fields.update(
                    {
                        "response_length": len(response_text),
                        "has_response": bool(response_text.strip()),
                        "response_preview": response_text[:200]
                        + ("..." if len(response_text) > 200 else response_text),
                    }
                )

                if evaluate_response:
                    eval_passed, eval_fields, warning_message = evaluate_response(result)
                    passed = passed and bool(eval_passed)
                    if eval_fields:
                        extra_fields.update(eval_fields)

                if passed:
                    self.performance_metrics["successful_requests"] += 1
                    if extra_fields.get("tool_calls_detected"):
                        self.performance_metrics["tool_calls_detected"] += 1

                    test_result = {
                        "test_case": test_case,
                        "task_id": conversation_request.task_id,
                        "model": model_name,
                        "status": "success",
                        "execution_time": execution_time,
                        "error_message": None,
                        "metadata": result.metadata,
                        "timestamp": datetime.now().isoformat(),
                        **extra_fields,
                    }
                    self.test_results.append(test_result)

                    if warning_message:
                        self.logger.warning(f"⚠️ {test_case} WARNING - {warning_message}")
                    return True

                # Evaluation failed despite successful status
                warning_message = warning_message or "Response did not meet evaluation criteria"
                self.logger.error(f"❌ {test_case} FAILED - {warning_message}")

            else:
                warning_message = result.error_message or "No response returned"
                self.logger.error(f"❌ {test_case} FAILED - {warning_message}")

            self.performance_metrics["failed_requests"] += 1
            test_result = {
                "test_case": test_case,
                "task_id": conversation_request.task_id,
                "model": model_name,
                "status": "failed",
                "execution_time": execution_time,
                "error_message": result.error_message or "No response returned",
                "timestamp": datetime.now().isoformat(),
            }
            self.test_results.append(test_result)
            return False

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["failed_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time

            self.logger.error(f"❌ {test_case} EXCEPTION - {str(e)}")
            test_result = {
                "test_case": test_case,
                "task_id": conversation_request.task_id,
                "model": model_name,
                "status": "exception",
                "execution_time": execution_time,
                "error_message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            self.test_results.append(test_result)
            return False

    def setup_logging(self):
        """Setup detailed logging for the test suite."""
        # Create logs directory
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Create timestamp for this test run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Setup file logger for detailed logs
        self.log_file = self.log_dir / f"complete_e2e_test_{timestamp}.log"
        
        # Configure logger
        self.logger = logging.getLogger(self.test_name)
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler for detailed logs
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler for important info
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.propagate = False

    async def setup(self):
        """Setup test environment with detailed logging."""
        self.logger.info("=" * 80)
        self.logger.info("COMPLETE E2E TEST SUITE - DETAILED REQUEST/RESPONSE LOGGING")
        self.logger.info("=" * 80)
        self.logger.info(f"Test started at: {self.start_time.isoformat()}")
        self.logger.info(f"Log file: {self.log_file}")
        
        # Environment check for all models
        self.logger.info(f"Testing models: {', '.join(self.test_models)}")
        
        for model in self.test_models:
            model_config = self.supported_models[model]
            api_key = os.getenv(model_config["api_key_env"], "")
            
            # Special handling for Azure models
            if model_config["provider"] == "azure_openai":
                endpoint = os.getenv(model_config["base_url"], "")
                deployment = os.getenv(model_config.get("deployment_name", ""), "")
                status = "Yes" if (api_key and api_key not in ['your-api-key-here', 'your-azure-openai-api-key'] 
                                  and endpoint and deployment) else "No"
                self.logger.info(f"{model} Azure API configured: {status}")
                if status == "Yes":
                    self.logger.debug(f"  Endpoint: {endpoint}")
                    self.logger.debug(f"  Deployment: {deployment}")
            else:
                status = "Yes" if api_key and api_key not in ['your-api-key-here', 'your-deepseek-api-key-here', 'your-openai-api-key-here'] else "No"
                self.logger.info(f"{model} API Key configured: {status}")
        
        self.logger.info(f"Python version: {sys.version}")
        
        try:
            self.logger.info("🚀 STEP 1: Initializing Aether Frame system...")
            self.logger.debug("Creating AI Assistant with timeout protection...")
            
            try:
                self.assistant = await asyncio.wait_for(
                    create_ai_assistant(self.settings), 
                    timeout=30.0
                )
                self.logger.info("✅ AI Assistant initialized successfully")
                self.logger.debug(f"Assistant type: {type(self.assistant).__name__}")
                
            except asyncio.TimeoutError:
                self.logger.error("❌ AI Assistant initialization timed out (30s)")
                return False
            except Exception as e:
                self.logger.error(f"❌ AI Assistant initialization failed: {str(e)}")
                return False
            
            # System health check
            self.logger.info("🔍 STEP 2: Performing system health check...")
            try:
                components = await create_system_components(self.settings)
                health_status = await health_check_system(components)
                
                self.logger.debug(f"Health check result: {json.dumps(health_status, indent=2)}")
                
                if health_status.get("overall_status") == "healthy":
                    self.logger.info("✅ System health check passed")
                else:
                    self.logger.warning(f"⚠️ System health check issues: {health_status}")
                    
            except Exception as e:
                self.logger.error(f"❌ Health check failed: {str(e)}")
                return False
            
            self.logger.info("✅ Setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Setup failed: {str(e)}")
            return False

    def log_request_details(self, task_request: TaskRequest, test_case: str, model: str = None):
        """Log detailed request information."""
        model_info = f" - Model: {model}" if model else ""
        self.logger.info(f"📤 REQUEST [{test_case}]{model_info} - Starting")
        self.logger.debug(f"Task ID: {task_request.task_id}")
        self.logger.debug(f"Task Type: {task_request.task_type}")
        self.logger.debug(f"Description: {task_request.description}")
        if model:
            self.logger.debug(f"Target Model: {model}")
        
        if task_request.messages:
            self.logger.debug(f"Messages Count: {len(task_request.messages)}")
            for i, msg in enumerate(task_request.messages):
                preview = self._summarize_message_content(msg.content)
                self.logger.debug(f"Message {i+1}: [{msg.role}] {preview}")
                if msg.metadata:
                    self.logger.debug(f"Message {i+1} metadata: {msg.metadata}")
        
        if task_request.metadata:
            self.logger.debug(f"Request metadata: {task_request.metadata}")

    def log_response_details(self, result, test_case: str, execution_time: float, model: str = None):
        """Log detailed response information."""
        model_info = f" - Model: {model}" if model else ""
        self.logger.info(f"📥 RESPONSE [{test_case}]{model_info} - Completed in {execution_time:.3f}s")
        self.logger.debug(f"Task ID: {result.task_id}")
        self.logger.debug(f"Status: {result.status.value if result.status else 'unknown'}")
        
        if result.messages:
            self.logger.debug(f"Response Messages Count: {len(result.messages)}")
            for i, msg in enumerate(result.messages):
                self.logger.debug(f"Response {i+1}: [{msg.role}] {msg.content}")
                if msg.metadata:
                    self.logger.debug(f"Response {i+1} metadata: {msg.metadata}")
        else:
            self.logger.debug("No response messages")
        
        if result.error_message:
            self.logger.debug(f"Error Message: {result.error_message}")
        
        if result.metadata:
            self.logger.debug(f"Response metadata: {result.metadata}")
        
        if result.result_data:
            self.logger.debug(f"Result data: {result.result_data}")

    async def test_simple_conversation(self, model: str = None):
        """Test simple conversation using two-step (creation + conversation) flow."""
        test_case = "simple_conversation"
        model_name = model or self.settings.default_model
        initial_message = UniversalMessage(
            role="user",
            content="Hello! Please tell me about yourself and what you can do.",
            metadata={"test_case": test_case, "expects_response": True},
        )

        return await self._run_conversation_test(
            test_case=test_case,
            model_name=model_name,
            agent_type="conversational_assistant",
            system_prompt="You are a helpful AI assistant.",
            messages=[initial_message],
            creation_metadata={"test_case": test_case},
        )

    async def test_multimodal_image_analysis(self, model: str = None):
        """Test multimodal image analysis with post-creation conversation."""
        test_case = "multimodal_image_analysis"
        model_name = model or self.settings.default_model

        tiny_png_base64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
        )
        image_ref = ImageReference.from_base64(
            f"data:image/png;base64,{tiny_png_base64}", image_format="png"
        )

        multimodal_message = UniversalMessage(
            role="user",
            content=[
                ContentPart(text="请简要描述这张图片的颜色。"),
                ContentPart(image_reference=image_ref),
            ],
            metadata={"test_case": test_case, "expects_image": True},
        )

        def evaluate_response(result):
            response_text = result.messages[0].content if result.messages else ""
            recognized_color = any(
                keyword in response_text.lower()
                for keyword in ["red", "green", "blue", "yellow", "色"]
            )
            warning = None
            if not recognized_color:
                warning = "Model response did not explicitly mention color keywords"
            return True, {"recognized_color": recognized_color}, warning

        return await self._run_conversation_test(
            test_case=test_case,
            model_name=model_name,
            agent_type="vision_assistant",
            system_prompt="你是一个多模态视觉助手，善于分析图像内容。",
            messages=[multimodal_message],
            creation_metadata={"expects_multimodal": True},
            conversation_metadata={"expects_multimodal": True},
            model_config={
                "model": model_name,
                "temperature": 0.2,
                "max_tokens": 800,
            },
            evaluate_response=evaluate_response,
        )

    async def test_tool_usage_request(self, model: str = None):
        """Test tool usage request with the new conversation flow."""
        test_case = "tool_usage_request"
        model_name = model or self.settings.default_model

        tool_message = UniversalMessage(
            role="user",
            content="Please use the chat_log tool to save this conversation content: 'Complete E2E test conversation for tool usage validation'. Use these exact parameters: content='Complete E2E test conversation for tool usage validation', format='json', session_id='e2e_test_session'.",
            metadata={"test_case": test_case, "expects_tool_call": True},
        )

        def evaluate_response(result):
            tool_used = False
            if result.messages:
                response_content = result.messages[0].content.lower()
                tool_indicators = ["chat_log", "saved", "logged", "tool", "file"]
                tool_used = any(indicator in response_content for indicator in tool_indicators)
            warning = None
            if not tool_used:
                warning = "Tool usage indicators not detected in response"
            return True, {"tool_calls_detected": tool_used}, warning

        return await self._run_conversation_test(
            test_case=test_case,
            model_name=model_name,
            agent_type="tool_assistant",
            system_prompt="You are a helpful AI assistant with access to tools.",
            messages=[tool_message],
            creation_metadata={"expects_tool_usage": True},
            conversation_metadata={"expects_tool_usage": True},
            model_config={
                "model": model_name,
                "temperature": 0.3,
                "max_tokens": 1500,
            },
            available_tools=["chat_log"],
            evaluate_response=evaluate_response,
        )

    async def test_complex_conversation(self, model: str = None):
        """Test complex conversation with evaluation of response quality."""
        test_case = "complex_conversation"
        model_name = model or self.settings.default_model

        complex_message = UniversalMessage(
            role="user",
            content="I'm working on a Python project and need help with the following: 1) Explain async/await in Python, 2) Give me a simple example, 3) Tell me when to use it vs regular functions. Please be comprehensive but concise.",
            metadata={"test_case": test_case, "complexity": "high"},
        )

        def evaluate_response(result):
            if not result.messages:
                return False, {"response_quality": {}}, "No response returned"
            content = result.messages[0].content.lower()
            response_quality = {
                "comprehensive": len(content) > 300,
                "has_examples": any(word in content for word in ["example", "def ", "async def", "await"]),
                "addresses_all_points": all(word in content for word in ["async", "await", "function"]),
            }
            quality_score = sum(response_quality.values())
            warning = None
            if quality_score < 2:
                warning = f"Lower quality response (score: {quality_score}/3)"
            return True, {"response_quality": response_quality}, warning

        return await self._run_conversation_test(
            test_case=test_case,
            model_name=model_name,
            agent_type="programming_assistant",
            system_prompt="You are an expert Python programming assistant.",
            messages=[complex_message],
            creation_metadata={"complexity_level": "high"},
            conversation_metadata={
                "complexity_level": "high",
                "expected_topics": ["async", "await", "python", "examples"],
                "test_case": test_case,
            },
            model_config={
                "model": model_name,
                "temperature": 0.2,
                "max_tokens": 2000,
            },
            evaluate_response=evaluate_response,
        )

    async def test_agent_reuse_same_config(self, model: str = None):
        """Validate that identical agent configs are reused until session capacity is exceeded."""
        test_case = "agent_reuse_same_config"
        model_name = model or self.settings.default_model
        start_time = datetime.now()

        user_context = self._build_user_context()
        shared_system_prompt = "You specialize in knowledge-base lookups and should maintain reusable state."
        shared_model_config = {
            "model": model_name,
            "temperature": 0.3,
            "max_tokens": 800,
        }

        initial_metadata = {
            "test_case": test_case,
            "chat_session_id": f"reuse_session_{uuid4().hex[:10]}",
        }

        first_agent_id, first_chat_id = await self._create_agent_and_session(
            model_name=model_name,
            agent_type="reuse_assistant",
            system_prompt=shared_system_prompt,
            initial_message=None,
            creation_task=f"reuse_create_1_{int(start_time.timestamp())}",
            creation_description="Create agent for reuse baseline",
            creation_metadata=initial_metadata,
            user_context=user_context,
            model_config=shared_model_config,
        )

        adk_adapter = await self.assistant.execution_engine.framework_registry.get_adapter(FrameworkType.ADK)
        if not adk_adapter:
            self.logger.error("❌ Agent reuse test aborted: ADK adapter unavailable")
            return False
        first_runner_id = adk_adapter._agent_runners.get(first_agent_id)

        self.logger.info(
            "🔄 Agent reuse test - initial agent created | agent_id=%s | runner_id=%s | chat_session_id=%s",
            first_agent_id,
            first_runner_id,
            first_chat_id,
        )

        second_metadata = {
            "test_case": test_case,
            "chat_session_id": f"reuse_session_{uuid4().hex[:10]}",
        }

        second_agent_id, second_chat_id = await self._create_agent_and_session(
            model_name=model_name,
            agent_type="reuse_assistant",
            system_prompt=shared_system_prompt,
            initial_message=None,
            creation_task=f"reuse_create_2_{int(datetime.now().timestamp())}",
            creation_description="Create agent for reuse verification",
            creation_metadata=second_metadata,
            user_context=user_context,
            model_config=shared_model_config,
        )

        second_runner_id = adk_adapter._agent_runners.get(second_agent_id)
        reuse_success = (second_agent_id == first_agent_id) and (second_runner_id == first_runner_id)

        self.logger.info(
            "🔁 Agent reuse attempt | agent_id=%s | runner_id=%s | reused=%s | chat_session_id=%s",
            second_agent_id,
            second_runner_id,
            reuse_success,
            second_chat_id,
        )

        overflow_success = False
        overflow_agent_id = None
        overflow_runner_id = None
        original_threshold = getattr(adk_adapter.runner_manager.settings, "max_sessions_per_agent", 100)

        runner_context = adk_adapter.runner_manager.runners.get(first_runner_id)
        try:
            adk_adapter.runner_manager.settings.max_sessions_per_agent = 1
            if runner_context is not None:
                runner_context.setdefault("sessions", {})["force_existing_session"] = {}

            overflow_metadata = {
                "test_case": test_case,
                "chat_session_id": f"reuse_session_{uuid4().hex[:10]}",
                "trigger": "threshold_overflow",
            }

            overflow_agent_id, overflow_chat_id = await self._create_agent_and_session(
                model_name=model_name,
                agent_type="reuse_assistant",
                system_prompt=shared_system_prompt,
                initial_message=None,
                creation_task=f"reuse_create_overflow_{int(datetime.now().timestamp())}",
                creation_description="Create agent after forcing session threshold",
                creation_metadata=overflow_metadata,
                user_context=user_context,
                model_config=shared_model_config,
            )

            overflow_runner_id = adk_adapter._agent_runners.get(overflow_agent_id)
            overflow_success = overflow_agent_id != first_agent_id

            self.logger.info(
                "♻️ Agent overflow attempt | agent_id=%s | runner_id=%s | new_agent=%s | chat_session_id=%s",
                overflow_agent_id,
                overflow_runner_id,
                overflow_success,
                overflow_chat_id,
            )
        finally:
            adk_adapter.runner_manager.settings.max_sessions_per_agent = original_threshold
            if runner_context is not None:
                runner_context.setdefault("sessions", {}).pop("force_existing_session", None)

        duration = (datetime.now() - start_time).total_seconds()
        success = reuse_success and overflow_success

        if success:
            self.logger.info("✅ Agent reuse behaviour validated: reuse occurred and new agent spawned when threshold exceeded")
        else:
            self.logger.error(
                "❌ Agent reuse behaviour failed: reuse_success=%s, overflow_success=%s",
                reuse_success,
                overflow_success,
            )

        self.test_results.append(
            {
                "test_case": test_case,
                "task_id": f"e2e_{test_case}_{int(datetime.now().timestamp())}",
                "model": model_name,
                "status": "success" if success else "failed",
                "execution_time": duration,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "first_agent_id": first_agent_id,
                    "second_agent_id": second_agent_id,
                    "overflow_agent_id": overflow_agent_id,
                    "first_runner_id": first_runner_id,
                    "second_runner_id": second_runner_id,
                    "overflow_runner_id": overflow_runner_id,
                    "reuse_success": reuse_success,
                    "overflow_success": overflow_success,
                    "model": model_name,
                },
            }
        )

        return success

    def generate_final_report(self):
        """Generate comprehensive final test report."""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        # Calculate performance metrics
        if self.performance_metrics["total_requests"] > 0:
            self.performance_metrics["average_response_time"] = (
                self.performance_metrics["total_execution_time"] / self.performance_metrics["total_requests"]
            )
            success_rate = (self.performance_metrics["successful_requests"] / self.performance_metrics["total_requests"]) * 100
        else:
            success_rate = 0.0
        
        # Environment info
        env_info = {
            "python_version": sys.version,
            "aether_frame_available": True,
            "deepseek_model": "deepseek-chat",
            "deepseek_api_configured": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
            "openai_api_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "azure_openai_api_configured": bool(os.getenv("AZURE_API_KEY", "").strip()),
            "azure_openai_endpoint_configured": bool(os.getenv("AZURE_API_BASE", "").strip()),
            "test_environment": "complete_e2e",
            "config_file": ".env.test"
        }
        
        # Generate report
        report = {
            "test_suite": "complete_e2e_test",
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_duration": total_duration,
            "performance_metrics": {
                **self.performance_metrics,
                "success_rate": success_rate
            },
            "test_results": self.test_results,
            "environment": env_info,
            "summary": {
                "total_tests": len(self.test_results),
                "passed_tests": len([r for r in self.test_results if r["status"] == "success"]),
                "failed_tests": len([r for r in self.test_results if r["status"] == "failed"]),
                "exception_tests": len([r for r in self.test_results if r["status"] == "exception"]),
            }
        }
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.log_dir / f"complete_e2e_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"✅ Complete E2E test report saved to: {report_file}")
        
        return report, report_file

    async def run_all_tests(self):
        """Run all tests in sequence with detailed logging and multi-model support."""
        self.logger.info("🚀 STARTING COMPLETE E2E TEST SUITE WITH MULTI-MODEL SUPPORT")
        self.logger.info("=" * 80)
        self.logger.info("EXECUTION FLOW:")
        self.logger.info("1. System Bootstrap & Initialization")
        self.logger.info("2. AI Assistant Creation")
        self.logger.info("3. System Health Check")
        self.logger.info("4. Multi-Model Test Execution:")
        for model in self.test_models:
            self.logger.info(f"   └── Model: {model}")
            self.logger.info("       ├── Test 1: Simple Conversation")
            self.logger.info("       ├── Test 2: Multimodal Image Analysis")
            self.logger.info("       ├── Test 3: Tool Usage Request")
            self.logger.info("       ├── Test 4: Complex Conversation")
            self.logger.info("       └── Test 5: Agent Config Reuse")
        self.logger.info("5. Report Generation & Summary")
        self.logger.info("=" * 80)
        
        try:
            # Setup - 必须等待完成
            self.logger.info("🔧 PHASE 1: SYSTEM SETUP")
            if not await self.setup():
                self.logger.error("❌ Setup failed, aborting tests")
                return False
            
            self.logger.info("✅ Setup completed, starting multi-model test execution...")
            
            # Run tests for each model
            all_model_results = []
            overall_success = True
            
            for i, model in enumerate(self.test_models, 1):
                self.logger.info(f"\n" + "="*60)
                self.logger.info(f"🔧 PHASE {i+1}: TESTING MODEL '{model}' ({i}/{len(self.test_models)})")
                self.logger.info("="*60)
                
                # Update settings for current model
                self.settings.default_model = model
                
                # Track model-specific results
                model_start_time = datetime.now()
                model_results = []
                
                # Test 1: Simple conversation
                self.logger.info(f"\n📋 [{model}] Starting Test 1: Simple Conversation...")
                result1 = await self.test_simple_conversation(model)
                model_results.append(("simple_conversation", result1))
                
                if result1:
                    self.logger.info(f"✅ [{model}] Test 1 COMPLETED: Simple Conversation - SUCCESS")
                else:
                    self.logger.error(f"❌ [{model}] Test 1 COMPLETED: Simple Conversation - FAILED")
                
                # Test 2: Multimodal image analysis
                self.logger.info(f"\n📋 [{model}] Starting Test 2: Multimodal Image Analysis...")
                result2 = await self.test_multimodal_image_analysis(model)
                model_results.append(("multimodal_image_analysis", result2))
                
                if result2:
                    self.logger.info(f"✅ [{model}] Test 2 COMPLETED: Multimodal Image Analysis - SUCCESS")
                else:
                    self.logger.error(f"❌ [{model}] Test 2 COMPLETED: Multimodal Image Analysis - FAILED")
                
                # Test 3: Tool usage
                self.logger.info(f"\n📋 [{model}] Starting Test 3: Tool Usage...")
                result3 = await self.test_tool_usage_request(model)
                model_results.append(("tool_usage_request", result3))
                
                if result3:
                    self.logger.info(f"✅ [{model}] Test 3 COMPLETED: Tool Usage - SUCCESS")
                else:
                    self.logger.error(f"❌ [{model}] Test 3 COMPLETED: Tool Usage - FAILED")
                
                # Test 4: Complex conversation
                self.logger.info(f"\n📋 [{model}] Starting Test 4: Complex Conversation...")
                result4 = await self.test_complex_conversation(model)
                model_results.append(("complex_conversation", result4))

                if result4:
                    self.logger.info(f"✅ [{model}] Test 4 COMPLETED: Complex Conversation - SUCCESS")
                else:
                    self.logger.error(f"❌ [{model}] Test 4 COMPLETED: Complex Conversation - FAILED")

                # Test 5: Agent config reuse behaviour
                self.logger.info(f"\n📋 [{model}] Starting Test 5: Agent Config Reuse...")
                result5 = await self.test_agent_reuse_same_config(model)
                model_results.append(("agent_reuse_same_config", result5))

                if result5:
                    self.logger.info(f"✅ [{model}] Test 5 COMPLETED: Agent Config Reuse - SUCCESS")
                else:
                    self.logger.error(f"❌ [{model}] Test 5 COMPLETED: Agent Config Reuse - FAILED")
                
                # Calculate model success rate
                model_success_count = sum(1 for _, success in model_results if success)
                model_success_rate = (model_success_count / len(model_results)) * 100
                model_duration = (datetime.now() - model_start_time).total_seconds()
                
                self.logger.info(f"\n📊 [{model}] Model Summary:")
                self.logger.info(f"   Tests Passed: {model_success_count}/{len(model_results)}")
                self.logger.info(f"   Success Rate: {model_success_rate:.1f}%")
                self.logger.info(f"   Duration: {model_duration:.2f}s")
                
                # Store model results
                self.performance_metrics["models_tested"].append(model)
                self.performance_metrics["model_results"][model] = {
                    "tests_passed": model_success_count,
                    "total_tests": len(model_results),
                    "success_rate": model_success_rate,
                    "duration": model_duration,
                    "results": model_results
                }
                
                all_model_results.extend([(f"{model}_{test}", result) for test, result in model_results])
                
                if model_success_count < len(model_results):
                    overall_success = False
            
            # Generate final report
            self.logger.info(f"\n" + "="*60)
            self.logger.info(f"🔧 PHASE {len(self.test_models)+2}: REPORT GENERATION")
            self.logger.info("="*60)
            self.logger.info("🎉 All model tests completed, generating final report...")
            report, report_file = self.generate_final_report()
            
            # Multi-model summary
            self.logger.info("\n" + "=" * 80)
            self.logger.info("COMPLETE E2E MULTI-MODEL TEST SUMMARY")
            self.logger.info("=" * 80)
            
            total_passed = 0
            total_tests = 0
            
            for model in self.test_models:
                model_data = self.performance_metrics["model_results"][model]
                passed = model_data["tests_passed"]
                total = model_data["total_tests"]
                rate = model_data["success_rate"]
                
                self.logger.info(f"🤖 {model}:")
                self.logger.info(f"   Passed: {passed}/{total} ({rate:.1f}%)")
                
                total_passed += passed
                total_tests += total
            
            overall_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
            
            self.logger.info(f"\n📊 Overall Results:")
            self.logger.info(f"   Models Tested: {len(self.test_models)}")
            self.logger.info(f"   Total Tests: {total_tests}")
            self.logger.info(f"   Total Passed: {total_passed}")
            self.logger.info(f"   Overall Success Rate: {overall_rate:.1f}%")
            self.logger.info(f"   Total Duration: {report['total_duration']:.2f}s")
            self.logger.info(f"   Average Response Time: {self.performance_metrics['average_response_time']:.2f}s")
            self.logger.info(f"   Tool Calls Detected: {self.performance_metrics['tool_calls_detected']}")
            
            self.logger.info(f"\n📋 Detailed log: {self.log_file}")
            self.logger.info(f"📋 Report file: {report_file}")
            
            if overall_success:
                self.logger.info("\n🎉 ALL TESTS PASSED ACROSS ALL MODELS!")
                return True
            else:
                self.logger.warning(f"\n⚠️ Some tests failed across models")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Test suite failed with exception: {str(e)}")
            return False


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Complete End-to-End Test Suite with Multi-Model Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_complete_e2e.py                          # Test with default model (deepseek-chat)
  python test_complete_e2e.py --models deepseek-chat   # Test with specific model
  python test_complete_e2e.py --models gpt-4o gpt-4.1  # Test with multiple OpenAI models
  python test_complete_e2e.py --models azure/gpt-4     # Test with Azure OpenAI
  python test_complete_e2e.py --all-models             # Test with all supported models
  python test_complete_e2e.py --list-models            # List supported models
        """
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--models", 
        nargs="+", 
        help="Specific models to test (deepseek-chat, gpt-4o, gpt-4.1, azure/gpt-4, azure/gpt-4o, azure-gpt-4)"
    )
    group.add_argument(
        "--all-models", 
        action="store_true", 
        help="Test all supported models"
    )
    group.add_argument(
        "--list-models", 
        action="store_true", 
        help="List all supported models and exit"
    )
    
    return parser.parse_args()


async def main():
    """Main test execution function with multi-model support."""
    args = parse_arguments()
    
    supported_models = ["deepseek-chat", "gpt-4o", "gpt-4.1", "azure/gpt-4", "azure/gpt-4o", "azure-gpt-4"]
    
    if args.list_models:
        print("🤖 Supported AI Models:")
        print("=" * 50)
        for model in supported_models:
            if "deepseek" in model:
                provider = "DeepSeek"
            elif model.startswith("azure/") or model.startswith("azure-"):
                provider = "Azure OpenAI"
            else:
                provider = "OpenAI"
            print(f"  • {model} ({provider})")
        print("\nUsage:")
        print("  python test_complete_e2e.py --models deepseek-chat")
        print("  python test_complete_e2e.py --models azure/gpt-4")
        print("  python test_complete_e2e.py --all-models")
        return
    
    print("🚀 Complete End-to-End Test Suite with Multi-Model Support")
    print("=" * 70)
    print("Features:")
    print("- Multi-model testing (DeepSeek, OpenAI, Azure OpenAI)")
    print("- Detailed request/response logging") 
    print("- Complete execution flow tracking")
    print("- Performance metrics collection")
    print("- Comprehensive test reporting")
    print("- Real AI model integration testing")
    print()
    
    try:
        test_suite = CompleteE2ETestSuite(
            models=args.models,
            run_all_models=args.all_models
        )
        
        print(f"🎯 Target Models: {', '.join(test_suite.test_models)}")
        print()
        
        success = await test_suite.run_all_tests()
        
        if success:
            print(f"\n🎉 Complete E2E test suite PASSED!")
            print(f"📋 Check detailed logs: {test_suite.log_file}")
            sys.exit(0)
        else:
            print(f"\n💥 Complete E2E test suite had FAILURES!")
            print(f"📋 Check detailed logs: {test_suite.log_file}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test suite failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
