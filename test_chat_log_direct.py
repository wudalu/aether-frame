#!/usr/bin/env python3
"""直接测试chat_log工具的功能"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from aether_frame.tools.builtin.chat_log_tool import ChatLogTool
from aether_frame.contracts import ToolRequest


async def test_chat_log_tool():
    """直接测试chat_log工具"""
    print("🧪 开始直接测试chat_log工具...")
    
    # 创建工具实例
    chat_log_tool = ChatLogTool()
    
    # 初始化工具
    print("🔧 初始化chat_log工具...")
    await chat_log_tool.initialize()
    
    # 创建测试请求
    tool_request = ToolRequest(
        tool_name="chat_log",
        tool_namespace="builtin",
        parameters={
            "content": "这是一个直接测试chat_log工具的内容",
            "session_id": "direct_test_session",
            "format": "json",
            "append": True,
        }
    )
    
    # 执行工具
    print("⚡ 执行chat_log工具...")
    result = await chat_log_tool.execute(tool_request)
    
    # 检查结果
    print(f"📋 工具执行结果:")
    print(f"  状态: {result.status.value}")
    print(f"  工具名: {result.tool_name}")
    print(f"  命名空间: {result.tool_namespace}")
    
    if result.result_data:
        print(f"  结果数据:")
        for key, value in result.result_data.items():
            print(f"    {key}: {value}")
    
    if result.error_message:
        print(f"  错误消息: {result.error_message}")
    
    # 检查文件是否被创建
    print("\n📁 检查生成的文件:")
    import os
    if os.path.exists("logs/sessions"):
        session_files = os.listdir("logs/sessions")
        print(f"  sessions目录文件: {session_files}")
    else:
        print("  sessions目录不存在")
        
    if os.path.exists("logs/chats"):
        chat_files = os.listdir("logs/chats")
        print(f"  chats目录文件: {chat_files}")
    else:
        print("  chats目录不存在")


if __name__ == "__main__":
    asyncio.run(test_chat_log_tool())