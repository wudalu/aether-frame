# -*- coding: utf-8 -*-
"""Simple MCP server with streaming tool support for testing."""

import asyncio
import json
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

# Create MCP server with SSE support
mcp = FastMCP("streaming-test-server")


@mcp.tool()
def long_task(steps: int = 5) -> str:
    """A tool that performs a long task with progress updates."""
    import time
    
    result = []
    for i in range(steps):
        time.sleep(0.5)  # Simulate work
        result.append(f"Step {i+1}/{steps} completed")
    
    return "\n".join(result)


@mcp.tool()  
async def streaming_search(query: str) -> str:
    """A streaming search tool that returns results progressively."""
    # This would be a regular tool, but we can make the client handle it with streaming
    results = [
        f"Searching for '{query}'...",
        f"Found 10 results for '{query}'",
        f"Processing result 1: Document about {query}",
        f"Processing result 2: Article about {query}", 
        f"Processing result 3: Paper about {query}",
        f"Search completed for '{query}'"
    ]
    
    return "\n".join(results)


@mcp.tool()
async def notification_stream() -> str:
    """Start a notification stream - this simulates a streaming tool."""
    # This tool would trigger streaming notifications
    import time
    import random
    
    notifications = []
    for i in range(3):
        await asyncio.sleep(0.2)
        notification = f"Notification {i+1}: Event at {time.time():.2f}"
        notifications.append(notification)
    
    return "\n".join(notifications)


if __name__ == "__main__":
    # Configure server settings
    print("Starting MCP streaming test server with SSE support...")
    print("Server will be available at: http://localhost:8000/mcp")
    print("SSE endpoint: http://localhost:8000/sse")
    
    # Set host and port via settings
    mcp.settings.host = "localhost"
    mcp.settings.port = 8001
    
    # Run with SSE transport for real streaming
    mcp.run(transport="sse")