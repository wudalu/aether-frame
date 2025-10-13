# -*- coding: utf-8 -*-
"""Tool resolver for converting tool names to UniversalTool objects."""

import logging
from typing import List, Optional, Dict, Any

from aether_frame.contracts.contexts import UniversalTool, UserContext
from aether_frame.tools.service import ToolService


logger = logging.getLogger(__name__)


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not found or not accessible."""
    pass


class ToolResolver:
    """Tool resolver for converting tool names to UniversalTool objects.
    
    This resolver enables user-friendly tool name resolution, supporting both:
    - Full namespaced names: "mcp_server.search" 
    - Simplified names: "search" → "mcp_server.search"
    - Built-in tools: "echo" → "builtin.echo"
    
    The resolver also handles permissions and access control.
    """
    
    def __init__(self, tool_service: ToolService):
        """Initialize the tool resolver.
        
        Args:
            tool_service: The tool service instance for accessing available tools
        """
        self.tool_service = tool_service
        self._logger = logger
    
    async def resolve_tools(
        self, 
        tool_names: List[str], 
        user_context: Optional[UserContext] = None
    ) -> List[UniversalTool]:
        """Resolve tool names to UniversalTool objects.
        
        Args:
            tool_names: List of tool names to resolve (can be full or simplified names)
            user_context: Optional user context for permission checks
            
        Returns:
            List of resolved UniversalTool objects
            
        Raises:
            ToolNotFoundError: When a tool is not found or not accessible
        """
        resolved_tools = []
        available_tools = await self.tool_service.get_tools_dict()
        
        self._logger.debug(f"Resolving tools: {tool_names}")
        self._logger.debug(f"Available tools: {list(available_tools.keys())}")
        
        for tool_name in tool_names:
            try:
                universal_tool = await self._resolve_single_tool(
                    tool_name, available_tools, user_context
                )
                resolved_tools.append(universal_tool)
                self._logger.debug(f"✅ Resolved '{tool_name}' to '{universal_tool.name}'")
                
            except ToolNotFoundError as e:
                self._logger.error(f"❌ Failed to resolve tool '{tool_name}': {e}")
                raise
        
        self._logger.info(f"Successfully resolved {len(resolved_tools)} tools")
        return resolved_tools
    
    async def _resolve_single_tool(
        self, 
        tool_name: str,
        available_tools: Dict[str, Any],
        user_context: Optional[UserContext] = None
    ) -> UniversalTool:
        """Resolve a single tool name to UniversalTool object.
        
        Args:
            tool_name: Tool name to resolve
            available_tools: Dict of available tools from ToolService
            user_context: Optional user context for permission checks
            
        Returns:
            Resolved UniversalTool object
            
        Raises:
            ToolNotFoundError: When tool is not found or not accessible
        """
        
        # Strategy 1: Try exact full name match
        if tool_name in available_tools:
            tool_instance = available_tools[tool_name]
            universal_tool = self._tool_to_universal(tool_instance, tool_name)
            
            # Check permissions
            if await self._check_tool_permission(universal_tool, user_context):
                return universal_tool
            else:
                raise ToolNotFoundError(
                    f"Tool '{tool_name}' found but access denied for user"
                )
        
        # Strategy 2: Try simplified name matching (find tools ending with .{name})
        simplified_candidates = [
            full_name for full_name in available_tools.keys()
            if full_name.endswith(f".{tool_name}")
        ]
        
        if simplified_candidates:
            # If multiple candidates, prefer the first one (could add priority logic later)
            selected_tool_name = simplified_candidates[0]
            tool_instance = available_tools[selected_tool_name]
            universal_tool = self._tool_to_universal(tool_instance, selected_tool_name)
            
            # Check permissions
            if await self._check_tool_permission(universal_tool, user_context):
                self._logger.debug(
                    f"Resolved simplified name '{tool_name}' to '{selected_tool_name}'"
                )
                if len(simplified_candidates) > 1:
                    self._logger.warning(
                        f"Multiple candidates for '{tool_name}': {simplified_candidates}. "
                        f"Selected '{selected_tool_name}'"
                    )
                return universal_tool
            else:
                raise ToolNotFoundError(
                    f"Tool '{tool_name}' found as '{selected_tool_name}' but access denied"
                )
        
        # Strategy 3: Try partial matching (contains the name)
        partial_candidates = [
            full_name for full_name in available_tools.keys()
            if tool_name in full_name.split('.')[-1]  # Match against the final part
        ]
        
        if partial_candidates:
            selected_tool_name = partial_candidates[0]
            tool_instance = available_tools[selected_tool_name]
            universal_tool = self._tool_to_universal(tool_instance, selected_tool_name)
            
            if await self._check_tool_permission(universal_tool, user_context):
                self._logger.debug(
                    f"Resolved partial match '{tool_name}' to '{selected_tool_name}'"
                )
                if len(partial_candidates) > 1:
                    self._logger.warning(
                        f"Multiple partial matches for '{tool_name}': {partial_candidates}. "
                        f"Selected '{selected_tool_name}'"
                    )
                return universal_tool
            else:
                raise ToolNotFoundError(
                    f"Tool '{tool_name}' found as '{selected_tool_name}' but access denied"
                )
        
        # No matches found
        similar_tools = self._find_similar_tools(tool_name, available_tools.keys())
        suggestion_text = f". Did you mean: {', '.join(similar_tools)}" if similar_tools else ""
        
        raise ToolNotFoundError(
            f"Tool '{tool_name}' not found in available tools{suggestion_text}"
        )
    
    def _tool_to_universal(self, tool_instance: Any, tool_name: str) -> UniversalTool:
        """Convert a Tool instance to UniversalTool object.
        
        Args:
            tool_instance: The tool instance from ToolService
            tool_name: The full tool name
            
        Returns:
            UniversalTool object
        """
        # Extract namespace from full name
        parts = tool_name.split('.')
        namespace = parts[0] if len(parts) > 1 else "builtin"
        
        return UniversalTool(
            name=tool_name,
            description=getattr(tool_instance, 'description', f"Tool: {tool_name}"),
            parameters_schema=getattr(tool_instance, 'parameters_schema', {}),
            namespace=namespace,
            supports_streaming=getattr(tool_instance, 'supports_streaming', False),
            metadata={
                "resolver": "ToolResolver",
                "tool_type": type(tool_instance).__name__,
                "resolved_from": tool_name
            }
        )
    
    async def _check_tool_permission(
        self, 
        tool: UniversalTool, 
        user_context: Optional[UserContext] = None
    ) -> bool:
        """Check if user has permission to use the tool.
        
        Args:
            tool: The UniversalTool to check
            user_context: User context for permission validation
            
        Returns:
            True if user has permission, False otherwise
        """
        # For now, implement basic permission logic
        # This can be extended later with more sophisticated ACL
        
        if user_context is None:
            # No user context means system-level access - allow all tools
            return True
        
        # Get user permissions
        if user_context.permissions is None:
            # No permissions specified - allow builtin tools only by default
            return tool.namespace == "builtin"
        
        user_permissions = set(user_context.permissions.permissions)
        
        # Check if user has explicit permission for this tool
        if tool.name in user_permissions or tool.namespace in user_permissions:
            return True
        
        # Check for wildcard permissions
        if f"{tool.namespace}.*" in user_permissions:
            return True
        
        # For now, allow builtin tools for all users
        if tool.namespace == "builtin":
            return True
        
        # Default: deny access to protect against unauthorized tool usage
        self._logger.warning(f"Access denied for tool '{tool.name}' for user context")
        return False
    
    def _find_similar_tools(self, target_name: str, available_names: List[str]) -> List[str]:
        """Find tools with similar names for suggestions.
        
        Args:
            target_name: The name being searched for
            available_names: List of available tool names
            
        Returns:
            List of similar tool names (up to 3)
        """
        similar = []
        target_lower = target_name.lower()
        
        for name in available_names:
            # Check if target is a substring of the tool name
            if target_lower in name.lower():
                similar.append(name)
            # Check if the last part of the tool name contains target
            elif target_lower in name.split('.')[-1].lower():
                similar.append(name)
        
        # Return up to 3 most similar matches
        return similar[:3]
    
    async def list_available_tools(
        self, 
        namespace_filter: Optional[str] = None,
        user_context: Optional[UserContext] = None
    ) -> List[UniversalTool]:
        """List all available tools, optionally filtered by namespace.
        
        Args:
            namespace_filter: Optional namespace to filter by
            user_context: Optional user context for permission filtering
            
        Returns:
            List of available UniversalTool objects
        """
        available_tools = await self.tool_service.get_tools_dict(namespace=namespace_filter)
        universal_tools = []
        
        for tool_name, tool_instance in available_tools.items():
            universal_tool = self._tool_to_universal(tool_instance, tool_name)
            
            # Apply permission check
            if not await self._check_tool_permission(universal_tool, user_context):
                continue
            
            universal_tools.append(universal_tool)
        
        # Sort by namespace then by name for consistent output
        universal_tools.sort(key=lambda t: (t.namespace, t.name))
        
        self._logger.info(
            f"Listed {len(universal_tools)} available tools"
            f"{f' in namespace {namespace_filter}' if namespace_filter else ''}"
        )
        
        return universal_tools