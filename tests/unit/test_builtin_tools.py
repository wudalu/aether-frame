# -*- coding: utf-8 -*-
"""Tests for builtin tool implementations."""

from pathlib import Path

import pytest

from aether_frame.contracts import ToolRequest, ToolStatus
from aether_frame.tools.builtin.tools import EchoTool, TimestampTool
from aether_frame.tools.builtin.chat_log_tool import ChatLogTool


@pytest.mark.asyncio
async def test_echo_tool_echoes_message():
    tool = EchoTool()
    await tool.initialize()
    request = ToolRequest(tool_name="echo", parameters={"message": "hello"})
    result = await tool.execute(request)
    assert result.status == ToolStatus.SUCCESS
    assert result.result_data == {"echo": "hello"}
    assert await tool.validate_parameters({"message": "x"}) is True
    assert await tool.validate_parameters({}) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("format_type", ["iso", "unix", "readable", "unknown"])
async def test_timestamp_tool_formats(format_type):
    tool = TimestampTool()
    await tool.initialize()
    request = ToolRequest(tool_name="timestamp", parameters={"format": format_type})
    result = await tool.execute(request)
    assert result.status == ToolStatus.SUCCESS
    assert result.result_data["format"] == format_type


@pytest.mark.asyncio
async def test_chat_log_tool_writes_files(tmp_path, monkeypatch):
    tool = ChatLogTool()
    monkeypatch.setattr(tool, "_log_base_dir", tmp_path)
    monkeypatch.setattr(tool, "_session_logs_dir", tmp_path / "sessions")
    monkeypatch.setattr(tool, "_chat_logs_dir", tmp_path / "chats")
    await tool.initialize()

    request = ToolRequest(
        tool_name="chat_log",
        parameters={
            "content": {"message": "hi"},
            "session_id": "sess-1",
            "format": "json",
        },
    )
    result = await tool.execute(request)
    assert result.status == ToolStatus.SUCCESS
    file_path = Path(result.result_data["file_path"])
    assert file_path.exists()
    contents = file_path.read_text()
    assert '"message": "hi"' in contents

    # Text format without append
    request_text = ToolRequest(
        tool_name="chat_log",
        parameters={
            "content": "plain text",
            "format": "text",
            "append": False,
            "filename": "custom.log",
        },
    )
    text_result = await tool.execute(request_text)
    text_file = Path(text_result.result_data["file_path"])
    assert text_file.exists()
    assert "plain text" in text_file.read_text()

    invalid = await tool.execute(ToolRequest(tool_name="chat_log", parameters={"format": "yaml"}))
    assert invalid.status == ToolStatus.ERROR
