"""Common utility functions for Aether Frame."""

import asyncio
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from aether_frame.common.exceptions import TimeoutError


def generate_task_id() -> str:
    """Generate a unique task ID."""
    return str(uuid.uuid4())


def generate_agent_id(agent_type: str, domain: Optional[str] = None) -> str:
    """Generate a unique agent ID."""
    base = f"{agent_type}"
    if domain:
        base += f"-{domain}"
    timestamp = int(time.time())
    return f"{base}-{timestamp}-{str(uuid.uuid4())[:8]}"


def hash_string(text: str) -> str:
    """Generate SHA-256 hash of string."""
    return hashlib.sha256(text.encode()).hexdigest()


def current_timestamp() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def serialize_json(obj: Any) -> str:
    """Serialize object to JSON string."""
    return json.dumps(obj, default=str, ensure_ascii=False)


def deserialize_json(json_str: str) -> Any:
    """Deserialize JSON string to object."""
    return json.loads(json_str)


async def with_timeout(
    coro: Awaitable[Any], timeout: float, error_message: Optional[str] = None
) -> Any:
    """Execute coroutine with timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(
            error_message or f"Operation timed out after {timeout} seconds"
        )


def safe_get(dictionary: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from dictionary."""
    return dictionary.get(key, default)


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries."""
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def truncate_string(text: str, max_length: int = 100) -> str:
    """Truncate string to maximum length."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


class Timer:
    """Context manager for timing operations."""

    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.end_time = time.time()

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time
