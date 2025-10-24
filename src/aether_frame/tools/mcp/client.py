# -*- coding: utf-8 -*-
"""Enhanced MCP client with real streaming support via message handlers."""

import asyncio
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool as MCPTool
import mcp.types as types

from aether_frame.contracts.contexts import UniversalTool
from .config import MCPServerConfig


class MCPConnectionError(Exception):
    """Raised when MCP server connection fails."""
    pass


class MCPToolError(Exception):
    """Raised when MCP tool execution fails."""
    pass


class MCPClient:
    """Enhanced MCP client with real notification-based streaming support.
    
    This client uses MCP's notification system to receive real-time progress
    updates during tool execution, enabling true server-side streaming.
    
    Attributes:
        config: MCP server configuration
        _session: Active MCP client session
        _progress_handlers: Dict of progress token -> asyncio queues for events
    """
    
    def __init__(self, config: MCPServerConfig):
        """Initialize MCP client with server configuration.
        
        Args:
            config: MCP server configuration object
        """
        self.config = config
        self._session: Optional[ClientSession] = None
        self._connected = False
        self._progress_handlers: Dict[str, asyncio.Queue] = {}
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def _notification_handler(self, message) -> None:
        """Handle incoming notifications from MCP server.
        
        This handler receives server notifications like logging messages
        and resource change notifications. Progress events are now handled
        via the official progress_callback mechanism.
        """
        try:
            print(f"🔍 Received notification: {type(message)} - {message}")
            
            # Handle different message types
            if hasattr(message, 'method'):
                method = message.method
                params = getattr(message, 'params', {})
                
                if method == "notifications/message":
                    # Handle logging notification
                    level = params.get('level', 'info')
                    data = params.get('data', '')
                    print(f"🔍 Server log [{level}]: {data}")
                
                elif method == "notifications/resources/updated":
                    # Handle resource update notifications
                    print(f"📋 Resource updated: {params}")
                
                elif method == "notifications/resources/list_changed":
                    # Handle resource list change notifications
                    print(f"📋 Resource list changed")
                
                else:
                    print(f"📫 Other notification: {method} - {params}")
            
            # Handle typed notifications
            elif isinstance(message, types.ServerNotification):
                notification = message.root
                
                if isinstance(notification, types.LoggingMessageNotification):
                    params = notification.params
                    print(f"🔍 Server log [{params.level}]: {params.data}")
                
                elif isinstance(notification, types.ResourceUpdatedNotification):
                    print(f"📋 Resource updated: {notification.params.uri}")
                
                elif isinstance(notification, types.ResourceListChangedNotification):
                    print(f"📋 Resource list changed")
                
                elif isinstance(notification, types.ProgressNotification):
                    # Progress notifications are now handled via progress_callback
                    # We just log them for debugging
                    params = notification.params
                    print(f"📊 Progress notification (handled via callback): {params.progress}/{params.total} - {params.message}")
                
                else:
                    print(f"📫 Unhandled notification type: {type(notification)}")
            
            else:
                print(f"📫 Unknown message type: {type(message)}")
                
        except Exception as e:
            print(f"⚠️ Error handling notification: {e}")
            import traceback
            traceback.print_exc()
    
    async def connect(self) -> None:
        """Establish connection to MCP server with notification handling.
        
        Raises:
            MCPConnectionError: When connection to server fails
        """
        if self._connected and self._session:
            return
        
        try:
            await self._open_persistent_session()
            
            self._connected = True
            print(f"✅ Connected to MCP server with notification handling enabled")
            
        except Exception as e:
            await self.disconnect()
            raise MCPConnectionError(f"Failed to connect to MCP server: {e}")
    
    async def disconnect(self) -> None:
        """Close connection to MCP server."""
        # Clean up progress handlers
        for queue in self._progress_handlers.values():
            await queue.put(None)  # Signal end
        self._progress_handlers.clear()
        
        if hasattr(self, '_session_context') and self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except:
                pass
            self._session_context = None
        
        if hasattr(self, '_stream_context') and self._stream_context:
            try:
                await self._stream_context.__aexit__(None, None, None)
            except:
                pass
            self._stream_context = None
        
        self._session = None
        self._connected = False
    
    async def _open_persistent_session(self) -> None:
        """Open persistent session using base configuration headers."""
        self._stream_context = streamablehttp_client(
            url=self.config.endpoint,
            headers=self.config.headers,
            timeout=self.config.timeout
        )
        read_stream, write_stream, _ = await self._stream_context.__aenter__()
        self._session_context = ClientSession(
            read_stream,
            write_stream,
            message_handler=self._notification_handler
        )
        self._session = await self._session_context.__aenter__()
        await self._session.initialize()

    async def _ensure_persistent_connection(self) -> None:
        """Ensure persistent connection is established."""
        if not self._connected or not self._session:
            await self.connect()

    @asynccontextmanager
    async def _session_scope(self, extra_headers: Optional[Dict[str, str]] = None):
        """Context manager yielding session with merged headers."""
        if extra_headers:
            merged_headers = dict(self.config.headers)
            merged_headers.update({str(k): str(v) for k, v in extra_headers.items()})
            temp_stream_context = streamablehttp_client(
                url=self.config.endpoint,
                headers=merged_headers,
                timeout=self.config.timeout
            )
            read_stream, write_stream, _ = await temp_stream_context.__aenter__()
            temp_session_context = ClientSession(
                read_stream,
                write_stream,
                message_handler=self._notification_handler
            )
            temp_session = await temp_session_context.__aenter__()
            await temp_session.initialize()
            try:
                yield temp_session
            finally:
                await temp_session_context.__aexit__(None, None, None)
                await temp_stream_context.__aexit__(None, None, None)
        else:
            await self._ensure_persistent_connection()
            yield self._session
    
    async def discover_tools(self, cursor: Optional[str] = None) -> List[UniversalTool]:
        """Discover available tools from MCP server.
        
        Args:
            cursor: Optional cursor for pagination
            
        Returns:
            List of UniversalTool objects representing available tools
            
        Raises:
            MCPConnectionError: When not connected to server
            MCPToolError: When tool discovery fails
        """
        if not self._connected or not self._session:
            raise MCPConnectionError("Not connected to MCP server")
        
        try:
            # Use official SDK to list tools
            tools_result = await self._session.list_tools(cursor=cursor)
            
            # Convert MCP tools to UniversalTool objects
            universal_tools = []
            for mcp_tool in tools_result.tools:
                universal_tool = self._convert_mcp_tool_to_universal(mcp_tool)
                universal_tools.append(universal_tool)
            
            return universal_tools
            
        except Exception as e:
            raise MCPToolError(f"Tool discovery failed: {e}")
    
    def _convert_mcp_tool_to_universal(self, mcp_tool: MCPTool) -> UniversalTool:
        """Convert MCP Tool to UniversalTool.
        
        Args:
            mcp_tool: MCP Tool object from the SDK
            
        Returns:
            UniversalTool object
        """
        # Add server namespace to tool name
        namespaced_name = f"{self.config.name}.{mcp_tool.name}"
        
        return UniversalTool(
            name=namespaced_name,
            description=mcp_tool.description,
            parameters_schema=mcp_tool.inputSchema if hasattr(mcp_tool, 'inputSchema') else {},
            namespace=self.config.name,
            supports_streaming=True,  # Now truly supports streaming!
            metadata={
                "mcp_server": self.config.name,
                "original_name": mcp_tool.name,
                "endpoint": self.config.endpoint,
                "mcp_tool_type": "streaming_enabled",
                "transport": "streamable_http_with_notifications"
            }
        )
    
    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Execute tool synchronously by collecting streaming result.
        
        This method now internally uses call_tool_stream and collects the final result,
        providing a unified interface while maintaining backward compatibility.
        
        Args:
            name: Tool name (without namespace prefix)  
            arguments: Tool execution arguments
            
        Returns:
            Tool execution result
            
        Raises:
            MCPConnectionError: When not connected to server
            MCPToolError: When tool execution fails
        """
        try:
            final_result = None
            async for chunk in self.call_tool_stream(
                name, arguments, extra_headers=extra_headers
            ):
                if chunk.get("type") == "complete_result" and chunk.get("is_final"):
                    final_result = chunk.get("content")
                    break
                elif chunk.get("type") == "error":
                    error_msg = chunk.get("error", "Tool execution failed")
                    raise MCPToolError(error_msg)
            
            if final_result is None:
                raise MCPToolError("No result received from tool execution")
                
            return final_result
            
        except MCPToolError:
            raise
        except MCPConnectionError:
            raise  # Keep connection errors as-is
        except Exception as e:
            raise MCPToolError(f"Tool execution failed: {e}")
    
    async def call_tool_stream(
        self, 
        name: str, 
        arguments: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute tool with REAL streaming via progress notifications.
        
        This implementation uses MCP's notification system to receive real-time
        progress updates from the server during tool execution.
        
        Args:
            name: Tool name (without namespace prefix)
            arguments: Tool execution arguments
            
        Yields:
            Real-time progress events and final result
            
        Raises:
            MCPConnectionError: When not connected to server
            MCPToolError: When tool execution fails
        """
        if not self._connected or not self._session:
            raise MCPConnectionError("Not connected to MCP server")
        
        try:
            start_time = time.time()
            
            # Generate unique progress token for this operation
            progress_token = f"stream_{int(time.time() * 1000)}_{hash(name) % 10000}"
            
            # Create progress event queue for this operation
            progress_queue = asyncio.Queue()
            self._progress_handlers[progress_token] = progress_queue
            
            # Emit start event
            yield {
                "type": "stream_start",
                "tool_name": name,
                "arguments": arguments,
                "progress_token": progress_token,
                "timestamp": start_time,
                "transport": "streamable_http_with_real_notifications"
            }
            
            # Create progress callback to capture progress events from MCP SDK
            async def progress_callback(progress: float, total: float = 1.0, message: str = ""):
                """Official MCP SDK progress callback function."""
                progress_event = {
                    "type": "progress_update",
                    "progress": progress,
                    "total": total,
                    "message": message,
                    "progress_token": progress_token,
                    "timestamp": time.time()
                }
                
                # Send to the appropriate progress handler queue
                if progress_token in self._progress_handlers:
                    queue = self._progress_handlers[progress_token]
                    await queue.put(progress_event)
                    print(f"✅ Progress via callback: {progress}/{total} - {message}")
            
            async with self._session_scope(extra_headers=extra_headers) as session:
                # Execute tool with official progress_callback parameter
                tool_task = asyncio.create_task(
                    session.call_tool(
                        name,
                        arguments,
                        progress_callback=progress_callback  # Official MCP SDK parameter!
                    )
                )
                
                # Monitor for progress events and tool completion
                while not tool_task.done():
                    try:
                        # Wait for progress event with short timeout
                        progress_event = await asyncio.wait_for(
                            progress_queue.get(), 
                            timeout=0.1
                        )
                        
                        if progress_event is None:
                            # End signal
                            break
                        
                        # Yield real-time progress event
                        yield progress_event
                        
                    except asyncio.TimeoutError:
                        # No progress event, continue monitoring
                        continue
                
                # Get the final result
                result = await tool_task
            end_time = time.time()
            
            # Yield any remaining progress events
            while True:
                try:
                    progress_event = progress_queue.get_nowait()
                    if progress_event is None:
                        break
                    yield progress_event
                except asyncio.QueueEmpty:
                    break
            
            # Extract content from result
            if hasattr(result, 'content') and result.content:
                if len(result.content) == 1:
                    content_item = result.content[0]
                    if hasattr(content_item, 'text'):
                        final_content = content_item.text
                    elif hasattr(content_item, 'data'):
                        final_content = content_item.data
                    else:
                        final_content = content_item
                else:
                    final_content = result.content
            else:
                final_content = result
            
            # Return complete result
            yield {
                "type": "complete_result",
                "content": final_content,
                "tool_name": name,
                "progress_token": progress_token,
                "timestamp": end_time,
                "total_time": end_time - start_time,
                "transport": "streamable_http_with_real_notifications",
                "is_final": True
            }
                
        except Exception as e:
            yield {
                "type": "error", 
                "error": str(e),
                "is_final": True,
                "tool_name": name,
                "timestamp": time.time(),
                "transport": "streamable_http_with_real_notifications"
            }
        finally:
            # Clean up progress handler
            if progress_token in self._progress_handlers:
                del self._progress_handlers[progress_token]
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected to server.
        
        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._session is not None
    
    @property
    def supports_streaming(self) -> bool:
        """Check if the client supports streaming.
        
        Returns:
            True - This client now supports real streaming via notifications
        """
        return True
