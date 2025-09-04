# Python 3.12 Enterprise Coding Standards

This document establishes enterprise-level coding standards based on Python 3.12's latest features for multi-agent application development, with a focus on user story generation system requirements.

## 1. Code Style and Formatting

### 1.1 Core Principles (Strict PEP 8 Compliance)
- Follow PEP 8 coding standards (see https://peps.python.org/pep-0008/)
- Use Black formatter (version >= 23.0.0) for automatic formatting
- Line length limit of 88 characters (Black default, modern development standard)
- Use 4 spaces for indentation, strictly no tabs
- Files must be UTF-8 encoded
- No trailing whitespace allowed
- Files must end with exactly one newline

### 1.2 Blank Line Standards (PEP 8 Section: Blank Lines)
```python
# Top-level classes and functions separated by two blank lines
import os
import sys


class UserStoryAgent:
    pass


def main() -> None:
    pass


# Class methods separated by one blank line
class AnalysisEngine:
    def __init__(self) -> None:
        self.data = {}
    
    def analyze(self, content: str) -> dict[str, Any]:
        return {"result": "analyzed"}
    
    def process_results(self, results: dict[str, Any]) -> None:
        pass
```

### 1.3 String Quote Standards
```python
# Prefer double quotes to avoid escaping single quotes in strings
message = "User story generation successful"
error_msg = "Agent execution failed: 'timeout'"

# Docstrings must use triple double quotes
def generate_story(requirements: str) -> str:
    """Generate user story.
    
    Args:
        requirements: Requirements description
        
    Returns:
        Generated user story text
    """
    pass
```

### 1.4 Import Standards (PEP 8 Section: Imports)
```python
# Import order: standard library -> third-party -> local imports, separated by blank lines
from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Awaitable
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import BaseModel
import structlog

from ..agents import CoordinatorAgent
from ..tools import WebSearchTool
from .exceptions import AgentExecutionError

# Avoid wildcard imports (except when explicitly needed in __init__.py)
# Wrong: from module import *

# Import aliases should be concise and clear
import numpy as np
import pandas as pd
from datetime import datetime as dt
```

### 1.5 Whitespace in Expressions and Statements (PEP 8 Section: Whitespace)
```python
# Correct whitespace usage
def process_data(items: list[str], config: dict[str, Any] = None) -> list[str]:
    # Spaces around operators
    result = []
    count = len(items) + 10
    
    # Space after comma, not before
    coordinates = (x, y, z)
    
    # Dictionary and list formatting
    agent_config = {
        "name": "story_agent",
        "temperature": 0.7,
        "max_tokens": 4000,
    }
    
    # Spaces in function calls
    response = await llm_call(prompt=user_input, model="gemini-2.0-flash")
    
    # Spaces in list comprehensions
    filtered_items = [item.strip() for item in items if item]
    
    return result

# Wrong examples (avoid this style)
def bad_example(items:list[str],config:dict[str,Any]=None)->list[str]:
    result=[]
    count=len(items)+10
    coordinates=(x,y,z)
    response=await llm_call(prompt=user_input,model="gemini-2.0-flash")
    return result
```

### 1.6 Naming Conventions (PEP 8 Section: Naming Conventions)
```python
# Modules and packages: lowercase with underscores
# user_story_agent.py, story_generation/

# Class names: CapWords (PascalCase)
class UserStoryAgent:
    pass

class LLMResponseHandler:
    pass

# Functions and variables: lowercase with underscores
def process_user_story() -> str:
    analysis_result = "result"
    return analysis_result

def generate_epic_stories(requirements: list[str]) -> dict[str, Any]:
    processed_requirements = []
    story_metadata = {}
    return {"stories": processed_requirements, "meta": story_metadata}

# Constants: uppercase with underscores
MAX_RETRY_ATTEMPTS = 3
API_TIMEOUT_SECONDS = 30
DEFAULT_MODEL_NAME = "gemini-2.0-flash"

# Private attributes and methods: single leading underscore
class StoryProcessor:
    def __init__(self) -> None:
        self._internal_cache = {}
        self._processing_state = "idle"
    
    def _validate_input(self, data: str) -> bool:
        return bool(data.strip())

# Avoid names prohibited by PEP 8
# Don't use: l (lowercase L), O (uppercase O), I (uppercase i) as single-character variables
# Don't use Python built-in names as variables
# Wrong examples:
# list = [1, 2, 3]  # shadows built-in list type
# str = "hello"     # shadows built-in str type

# Correct examples:
items_list = [1, 2, 3]
message_str = "hello"
```

### 1.7 Comment Standards (PEP 8 Section: Comments)
```python
# Inline comments: at least two spaces from code, for brief explanations
def process_stories(stories: list[str]) -> list[str]:
    results = []  # Store processing results
    count = 0  # Processing counter
    
    # Block comments: explain code blocks below, same indentation as code
    # Iterate through all user stories for preprocessing
    # Including format cleaning, length validation, etc.
    for story in stories:
        if len(story.strip()) > 10:  # Minimum length check
            results.append(story.strip().capitalize())
            count += 1
    
    return results

# TODO and FIXME comment format
def analyze_requirements(text: str) -> dict[str, Any]:
    # TODO: Add support for multi-language requirements
    # FIXME: Handle exception cases with empty strings
    return {"analyzed": text}
```

### 1.8 Docstring Standards (PEP 257)
```python
def generate_user_stories(
    requirements: list[str], 
    template: str = "agile",
    include_acceptance_criteria: bool = True
) -> dict[str, Any]:
    """Generate user story collection.
    
    Generate user stories conforming to agile development standards based on 
    requirement descriptions. Supports multiple template formats and optional 
    acceptance criteria generation.
    
    Args:
        requirements: List of requirement descriptions, each element is one requirement
        template: Story template type, supports "agile", "safe", "custom"
        include_acceptance_criteria: Whether to include acceptance criteria
    
    Returns:
        Dictionary containing the following keys:
        - stories: List of generated user stories
        - metadata: Metadata containing generation information
        - template_used: Template type used
    
    Raises:
        ValueError: When requirements is empty or template type is not supported
        AgentExecutionError: When LLM call fails
        
    Example:
        >>> requirements = ["User needs to view order history"]
        >>> result = generate_user_stories(requirements, template="agile")
        >>> print(result["stories"][0])
        "As a user, I want to view my order history..."
    """
    if not requirements:
        raise ValueError("Requirements list cannot be empty")
    
    # Implementation logic
    pass
```

## 2. Type Annotations and Static Type Checking

### 2.1 Mandatory Type Annotations (Based on Python 3.12 Features)
```python
from typing import Any, Dict, List, Optional, Union
from collections.abc import Callable, Awaitable

# Prefer Python 3.12 built-in types, reduce typing module dependencies
# Use built-in types: list, dict, tuple, set
def process_requirements(
    requirements: list[str], 
    config: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Process requirements list, return structured data."""
    if config is None:
        config = {}
    
    results = []
    for req in requirements:
        result = {"content": req, "processed": True}
        results.append(result)
    
    return results

# Async function type annotations - typical user story generation system scenario
async def generate_stories_with_llm(
    prompt: str,
    model_config: dict[str, Any],
    max_retries: int = 3
) -> dict[str, Any]:
    """Generate user stories using LLM."""
    # Implementation logic for async calls
    pass

# Class attribute type annotations - core agent system classes
class UserStoryAgent:
    """User story generation agent."""
    
    # Class variable type annotations
    max_items: int = 100
    default_temperature: float = 0.7
    supported_models: list[str] = [
        "gemini-2.0-flash",
        "gemini-2.0-pro", 
        "claude-3-5-sonnet-20241022"
    ]
    
    def __init__(self, config: dict[str, Any]) -> None:
        # Instance variable type annotations
        self.config: dict[str, Any] = config
        self.cache: dict[str, Any] = {}
        self._session_id: str = ""
        self._is_active: bool = False
```

### 2.2 Python 3.12 New Features Application

#### 2.2.1 Type Parameter Syntax (PEP 695) - Generic Simplification
```python
# Python 3.12 new generic syntax - more concise type parameter definitions
def process_items[T](items: list[T]) -> list[T]:
    """Process arbitrary type item list, filter null values."""
    return [item for item in items if item is not None]

# Generic class for user story generation system
class DataContainer[T]:
    """Generic data container, suitable for different types of agent data."""
    
    def __init__(self, data: T) -> None:
        self.data = data
        self.created_at = datetime.now()
    
    def get_data(self) -> T:
        return self.data
    
    def update_data(self, new_data: T) -> None:
        self.data = new_data

# Practical application example: process various types of AI responses
def process_llm_responses[ResponseType](
    responses: list[ResponseType]
) -> list[ResponseType]:
    """Process response data from different LLMs."""
    return [resp for resp in responses if hasattr(resp, 'content')]
```

#### 2.2.2 Union Types with | Operator (PEP 604)
```python
# Use | operator instead of Union, more concise code
def handle_agent_input(
    data: str | dict[str, Any] | list[str]
) -> dict[str, Any]:
    """Handle various input formats from agents."""
    if isinstance(data, str):
        return {"content": data, "type": "text"}
    elif isinstance(data, dict):
        return data
    else:  # list[str]
        return {"content": data, "type": "list"}

# Modern optional parameter syntax
def generate_story_variants(
    base_story: str,
    options: dict[str, bool] | None = None
) -> list[str]:
    """Generate multiple variants of user story."""
    if options is None:
        options = {}
    
    variants = [base_story]
    # Generation logic...
    return variants
```

#### 2.2.3 Enhanced Error Messages and Exception Groups
```python
# Python 3.11+ exception groups for handling concurrent multi-agent errors
import asyncio
from typing import Any

async def execute_multiple_agents(
    agents: list[Any],
    tasks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Execute multiple agent tasks in parallel, collect all errors."""
    async def run_single_agent(agent: Any, task: dict[str, Any]) -> dict[str, Any]:
        try:
            return await agent.execute(task)
        except Exception as e:
            # In Python 3.11+, can use more detailed error messages
            raise AgentExecutionError(
                f"Agent {agent.name} failed on task {task.get('id', 'unknown')}"
            ) from e
    
    try:
        # Use asyncio.gather to handle exception groups
        results = await asyncio.gather(
            *[run_single_agent(agent, task) for agent, task in zip(agents, tasks)],
            return_exceptions=True
        )
        
        # Separate successful and failed results
        successful_results = []
        exceptions = []
        
        for result in results:
            if isinstance(result, Exception):
                exceptions.append(result)
            else:
                successful_results.append(result)
        
        # If there are exceptions, consider using ExceptionGroup (Python 3.11+)
        if exceptions:
            logger.warning(f"Found {len(exceptions)} agent execution errors")
            # Decide whether to raise exception or continue processing
        
        return successful_results
        
    except* AgentExecutionError as eg:  # Python 3.11+ exception group syntax
        # Handle specific type exception groups
        logger.error(f"Multiple agent execution errors: {len(eg.exceptions)}")
        raise
```

## 3. Error Handling and Exception Management (Enterprise Best Practices)

### 3.1 Exception Hierarchy Design
```python
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Establish clear exception hierarchy
class UserStoryBotError(Exception):
    """Base exception class for user story bot."""
    
    def __init__(
        self, 
        message: str, 
        error_code: str | None = None,
        context: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.timestamp = datetime.now()

class AgentExecutionError(UserStoryBotError):
    """Agent execution exception."""
    
    def __init__(
        self, 
        message: str, 
        agent_id: str, 
        error_code: str | None = None,
        context: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message, error_code, context)
        self.agent_id = agent_id

class LLMAPIError(UserStoryBotError):
    """LLM API call exception."""
    
    def __init__(
        self,
        message: str,
        model_name: str,
        api_endpoint: str,
        status_code: int | None = None,
        error_code: str | None = None
    ) -> None:
        super().__init__(message, error_code)
        self.model_name = model_name
        self.api_endpoint = api_endpoint
        self.status_code = status_code

class ValidationError(UserStoryBotError):
    """Data validation exception."""
    
    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        invalid_value: Any = None
    ) -> None:
        super().__init__(message, "VALIDATION_ERROR")
        self.field_name = field_name
        self.invalid_value = invalid_value

# Exception handling best practices
async def execute_agent_task(
    agent_id: str,
    task_data: dict[str, Any]
) -> dict[str, Any]:
    """Standard error handling pattern for executing agent tasks."""
    try:
        # Input validation
        if not task_data.get("requirements"):
            raise ValidationError(
                "Missing required 'requirements' field in task data",
                field_name="requirements",
                invalid_value=task_data.get("requirements")
            )
        
        # Execute task logic
        result = await _perform_agent_task(agent_id, task_data)
        
        # Result validation
        if not result or "content" not in result:
            raise AgentExecutionError(
                "Agent returned invalid result format",
                agent_id=agent_id,
                error_code="INVALID_RESULT",
                context={"result_keys": list(result.keys()) if result else []}
            )
        
        logger.info(
            f"Agent task executed successfully",
            extra={
                "agent_id": agent_id,
                "task_id": task_data.get("id"),
                "execution_time_ms": result.get("execution_time")
            }
        )
        return result
        
    except ValidationError as e:
        logger.error(
            f"Task data validation failed - Agent: {agent_id}",
            extra={
                "agent_id": agent_id,
                "field_name": e.field_name,
                "error_code": e.error_code
            }
        )
        raise  # Re-raise for upper layer handling
        
    except LLMAPIError as e:
        logger.error(
            f"LLM API call failed - Agent: {agent_id}",
            extra={
                "agent_id": agent_id,
                "model_name": e.model_name,
                "status_code": e.status_code,
                "api_endpoint": e.api_endpoint
            }
        )
        # Convert to agent execution exception with better context
        raise AgentExecutionError(
            f"Agent {agent_id} LLM call failed: {e.message}",
            agent_id=agent_id,
            error_code="LLM_API_FAILURE",
            context={
                "original_error": str(e),
                "model_name": e.model_name,
                "status_code": e.status_code
            }
        ) from e
        
    except Exception as e:
        logger.exception(
            f"Unexpected exception in agent task execution - Agent: {agent_id}",
            extra={"agent_id": agent_id}
        )
        raise AgentExecutionError(
            f"Agent {agent_id} execution error: {str(e)}",
            agent_id=agent_id,
            error_code="UNEXPECTED_ERROR",
            context={"original_exception": type(e).__name__}
        ) from e
```

### 3.2 Resource Management and Context Managers
```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncio

@asynccontextmanager
async def agent_session(
    agent_id: str,
    config: dict[str, Any] | None = None
) -> AsyncGenerator[Any, None]:
    """Agent session context manager - ensures proper resource cleanup."""
    session = None
    session_start_time = datetime.now()
    
    try:
        # Create session
        session = await create_agent_session(agent_id, config)
        logger.info(
            f"Agent session created successfully: {agent_id}",
            extra={
                "agent_id": agent_id,
                "session_id": session.id,
                "start_time": session_start_time.isoformat()
            }
        )
        
        yield session
        
    except Exception as e:
        session_duration = (datetime.now() - session_start_time).total_seconds()
        logger.error(
            f"Agent session exception {agent_id}: {e}",
            extra={
                "agent_id": agent_id,
                "session_duration_seconds": session_duration,
                "error_type": type(e).__name__
            }
        )
        raise
        
    finally:
        if session:
            try:
                session_duration = (datetime.now() - session_start_time).total_seconds()
                await session.close()
                logger.info(
                    f"Agent session closed normally: {agent_id}",
                    extra={
                        "agent_id": agent_id,
                        "session_duration_seconds": session_duration
                    }
                )
            except Exception as cleanup_error:
                logger.warning(
                    f"Exception during agent session cleanup {agent_id}: {cleanup_error}",
                    extra={"agent_id": agent_id}
                )

# Timeout and retry mechanisms
class RetryConfig:
    """Retry configuration class."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

async def execute_with_retry[T](
    operation: Callable[[], Awaitable[T]],
    retry_config: RetryConfig,
    retriable_exceptions: tuple[type[Exception], ...] = (LLMAPIError,)
) -> T:
    """Operation executor with retry mechanism."""
    last_exception = None
    
    for attempt in range(retry_config.max_attempts):
        try:
            return await operation()
            
        except retriable_exceptions as e:
            last_exception = e
            if attempt == retry_config.max_attempts - 1:
                # Last attempt failed
                break
                
            # Calculate delay time (exponential backoff)
            delay = min(
                retry_config.base_delay * (retry_config.exponential_base ** attempt),
                retry_config.max_delay
            )
            
            logger.warning(
                f"Operation failed, retrying in {delay:.1f}s (attempt {attempt + 1}/{retry_config.max_attempts})",
                extra={
                    "attempt": attempt + 1,
                    "max_attempts": retry_config.max_attempts,
                    "delay_seconds": delay,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e)
                }
            )
            
            await asyncio.sleep(delay)
        
        except Exception as e:
            # Non-retriable exception, raise immediately
            logger.error(f"Operation failed with non-retriable exception: {e}")
            raise
    
    # All retries failed
    logger.error(
        f"Operation failed after maximum retry attempts ({retry_config.max_attempts})",
        extra={
            "max_attempts": retry_config.max_attempts,
            "final_exception": str(last_exception)
        }
    )
    raise last_exception
```

## 8. Code Quality and Security Standards (Production Environment)

### 8.1 Development Tool Configuration
```toml
# pyproject.toml - Basic configuration template (Production details TBD)

[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "user-story-bot"
version = "1.0.0"
description = "Enterprise Multi-Agent User Story Generation System"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0.0",
    "google-adk[all]>=1.0.0",
    "structlog>=23.0.0",
    # Additional production dependencies TBD
]

[tool.black]
line-length = 88
target-version = ['py312']

[tool.mypy]
python_version = "3.12"
strict = true

# Additional tool configurations TBD based on production requirements
```

### 8.2 Security Framework (Production Implementation TBD)
```python
# Security framework placeholder - detailed implementation TBD

class SecurityConfig:
    """Security configuration management."""
    # Production security patterns TBD
    pass

class SecurityManager:
    """Security manager for production environment."""
    
    def validate_input(self, user_input: str) -> str:
        """Input validation - implementation TBD."""
        pass
    
    def generate_session_token(self, user_id: str) -> str:
        """Session token generation - implementation TBD."""
        pass
    
    def rate_limit_check(self, client_id: str) -> bool:
        """Rate limiting - implementation TBD."""
        pass

class SecurityError(Exception):
    """Security exception class."""
    pass

# Authentication decorators and file handlers TBD
```

## Summary and Best Practices

This document provides comprehensive Python 3.12 coding standards for enterprise multi-agent systems. Key takeaways:

1. **Strict PEP 8 Compliance**: Follow all PEP 8 guidelines with modern tooling (Black, Ruff, mypy)
2. **Python 3.12 Features**: Leverage new generic syntax, union operators, and enhanced error handling
3. **Type Safety**: Use comprehensive type annotations with static type checking
4. **Security First**: Implement robust input validation, authentication, and audit logging
5. **Error Handling**: Design clear exception hierarchies with proper context management
6. **Performance**: Use async programming best practices with resource management
7. **Testing**: Maintain high test coverage with proper mocking and integration tests

These standards ensure code maintainability, security, and performance for production enterprise applications.