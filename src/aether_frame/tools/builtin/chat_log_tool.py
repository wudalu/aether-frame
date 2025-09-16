# -*- coding: utf-8 -*-
"""Chat Log Tool - Save chat conversations to local files."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...contracts import ToolRequest, ToolResult, ToolStatus
from ..base.tool import Tool


class ChatLogTool(Tool):
    """
    Chat log tool for saving conversation history to local files.

    Supports multiple output formats (JSON, text) and follows ADK naming conventions
    for log file organization. Creates structured directory layout for better
    log management.
    """

    def __init__(self):
        """Initialize chat log tool."""
        super().__init__("chat_log", "builtin")
        self._log_base_dir = Path("logs")
        self._session_logs_dir = self._log_base_dir / "sessions"
        self._chat_logs_dir = self._log_base_dir / "chats"

    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Initialize chat log tool and create directory structure."""
        self._config = config or {}
        
        # Create log directories following ADK conventions
        self._log_base_dir.mkdir(exist_ok=True)
        self._session_logs_dir.mkdir(exist_ok=True)
        self._chat_logs_dir.mkdir(exist_ok=True)
        
        # Create .gitignore for logs directory if it doesn't exist
        gitignore_path = self._log_base_dir / ".gitignore"
        if not gitignore_path.exists():
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write("# ADK Aether Frame Log Files\n")
                f.write("*.log\n")
                f.write("*.json\n")
                f.write("sessions/\n")
                f.write("chats/\n")
        
        self._initialized = True

    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        """
        Execute chat log tool to save conversation data.

        Parameters:
            - content: Chat content to save (string or dict)
            - session_id: Optional session identifier
            - format: Output format ('json' or 'text', default: 'json')
            - append: Whether to append to existing file (default: true)
            - filename: Optional custom filename (default: auto-generated)

        Returns:
            ToolResult: Result containing file path and metadata
        """
        try:
            # Extract parameters
            content = tool_request.parameters.get("content", "")
            session_id = tool_request.parameters.get("session_id")
            output_format = tool_request.parameters.get("format", "json")
            append_mode = tool_request.parameters.get("append", True)
            custom_filename = tool_request.parameters.get("filename")

            # Validate parameters
            if not content:
                return ToolResult(
                    tool_name=self.name,
                    tool_namespace=self.namespace,
                    status=ToolStatus.ERROR,
                    error_message="Content parameter is required",
                )

            # Generate filename following ADK conventions
            timestamp = datetime.now()
            if custom_filename:
                filename = custom_filename
            elif session_id:
                # Session-based filename: session_SESSIONID_YYYYMMDD.format
                date_str = timestamp.strftime("%Y%m%d")
                filename = f"session_{session_id}_{date_str}.{output_format}"
                target_dir = self._session_logs_dir
            else:
                # General chat log: chat_YYYYMMDD_HHMMSS.format
                datetime_str = timestamp.strftime("%Y%m%d_%H%M%S")
                filename = f"chat_{datetime_str}.{output_format}"
                target_dir = self._chat_logs_dir

            # Determine target directory
            if custom_filename:
                target_dir = self._chat_logs_dir
            elif session_id:
                target_dir = self._session_logs_dir
            else:
                target_dir = self._chat_logs_dir

            file_path = target_dir / filename

            # Prepare content for saving
            log_entry = {
                "timestamp": timestamp.isoformat(),
                "session_id": session_id,
                "content": content,
                "tool_execution": {
                    "tool_name": self.name,
                    "tool_namespace": self.namespace,
                    "execution_time": timestamp.isoformat(),
                }
            }

            # Save based on format
            if output_format == "json":
                await self._save_json_log(file_path, log_entry, append_mode)
            elif output_format == "text":
                await self._save_text_log(file_path, log_entry, append_mode)
            else:
                return ToolResult(
                    tool_name=self.name,
                    tool_namespace=self.namespace,
                    status=ToolStatus.ERROR,
                    error_message=f"Unsupported format: {output_format}",
                )

            # Return success result
            return ToolResult(
                tool_name=self.name,
                tool_namespace=self.namespace,
                status=ToolStatus.SUCCESS,
                result_data={
                    "file_path": str(file_path),
                    "filename": filename,
                    "format": output_format,
                    "append_mode": append_mode,
                    "content_size": len(str(content)),
                    "session_id": session_id,
                },
                created_at=timestamp,
            )

        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                tool_namespace=self.namespace,
                status=ToolStatus.ERROR,
                error_message=f"Failed to save chat log: {str(e)}",
                created_at=datetime.now(),
            )

    async def _save_json_log(
        self, file_path: Path, log_entry: Dict[str, Any], append_mode: bool
    ):
        """Save log entry as JSON format."""
        if append_mode and file_path.exists():
            # Read existing content
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
            except (json.JSONDecodeError, FileNotFoundError):
                existing_data = []
            
            # Append new entry
            existing_data.append(log_entry)
            
            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
        else:
            # Write new file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([log_entry], f, indent=2, ensure_ascii=False)

    async def _save_text_log(
        self, file_path: Path, log_entry: Dict[str, Any], append_mode: bool
    ):
        """Save log entry as text format."""
        # Format text entry
        text_content = f"[{log_entry['timestamp']}]"
        if log_entry['session_id']:
            text_content += f" Session: {log_entry['session_id']}"
        text_content += f"\n{log_entry['content']}\n"
        text_content += "-" * 80 + "\n"

        # Write to file
        mode = "a" if append_mode else "w"
        with open(file_path, mode, encoding="utf-8") as f:
            f.write(text_content)

    async def get_schema(self) -> Dict[str, Any]:
        """Get chat log tool schema."""
        return {
            "name": "chat_log",
            "description": "Save chat conversations to local files with ADK-compliant organization",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": ["string", "object"],
                        "description": "Chat content to save (text or structured data)"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session identifier for organizing logs"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "text"],
                        "default": "json",
                        "description": "Output format for the log file"
                    },
                    "append": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to append to existing file"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional custom filename (overrides auto-generation)"
                    }
                },
                "required": ["content"],
            },
        }

    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate chat log tool parameters."""
        # Content is required
        if "content" not in parameters:
            return False
        
        # Validate format if provided
        if "format" in parameters:
            if parameters["format"] not in ["json", "text"]:
                return False
        
        # Validate append if provided
        if "append" in parameters:
            if not isinstance(parameters["append"], bool):
                return False
        
        return True

    async def get_capabilities(self) -> List[str]:
        """Get chat log tool capabilities."""
        return [
            "save_conversation",
            "json_format",
            "text_format", 
            "session_grouping",
            "append_mode",
            "adk_compliant_naming",
            "auto_directory_creation"
        ]

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on chat log tool."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "log_directories": {
                "base": str(self._log_base_dir),
                "sessions": str(self._session_logs_dir),
                "chats": str(self._chat_logs_dir),
            },
            "directories_exist": {
                "base": self._log_base_dir.exists(),
                "sessions": self._session_logs_dir.exists(),
                "chats": self._chat_logs_dir.exists(),
            }
        }

    async def cleanup(self):
        """Cleanup chat log tool."""
        self._initialized = False