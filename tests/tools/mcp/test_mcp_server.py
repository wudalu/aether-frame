#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple MCP test server with basic tools for testing our MCPClient implementation."""

from mcp.server.fastmcp import FastMCP
import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("test-mcp-server")

@mcp.tool()
def echo(text: str) -> str:
    """Echo the provided text back to the caller.
    
    Args:
        text: The text to echo back
        
    Returns:
        The same text that was provided
    """
    logger.info(f"Echo tool called with: {text}")
    return f"Echo: {text}"

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        The sum of a and b
    """
    logger.info(f"Add tool called with: a={a}, b={b}")
    result = a + b
    return result

@mcp.tool()
def get_timestamp() -> str:
    """Get the current timestamp.
    
    Returns:
        Current timestamp in ISO format
    """
    logger.info("Timestamp tool called")
    timestamp = datetime.datetime.now().isoformat()
    return timestamp

@mcp.tool()
def calculate(a: float, b: float, operation: str) -> float:
    """Perform basic math operations.
    
    Args:
        a: First number
        b: Second number  
        operation: Operation to perform (add, subtract, multiply, divide)
        
    Returns:
        Result of the calculation
        
    Raises:
        ValueError: If operation is not supported or division by zero
    """
    logger.info(f"Calculate tool called with: a={a}, b={b}, operation={operation}")
    
    operations = {
        "add": a + b,
        "subtract": a - b, 
        "multiply": a * b,
        "divide": a / b if b != 0 else None
    }
    
    if operation not in operations:
        raise ValueError(f"Unknown operation: {operation}. Supported: {list(operations.keys())}")
    
    if operation == "divide" and b == 0:
        raise ValueError("Division by zero is not allowed")
    
    result = operations[operation]
    logger.info(f"Calculate result: {result}")
    return result

if __name__ == "__main__":
    print("🚀 Starting test MCP server...")
    print("📊 Available tools:")
    print("  - echo(text: str) -> str")
    print("  - add(a: float, b: float) -> float") 
    print("  - get_timestamp() -> str")
    print("  - calculate(a: float, b: float, operation: str) -> float")
    print()
    print("🌐 Running on default port with streamable-http transport")
    print("⏹️  Press Ctrl+C to stop")
    print()
    
    try:
        # Run with streamable HTTP transport (port defaults to 8000)
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        logger.error(f"Server error: {e}")
        print(f"❌ Server failed to start: {e}")