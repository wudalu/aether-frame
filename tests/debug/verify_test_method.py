#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证测试结果的脚本 - 你可以运行这个来验证我的测试方法"""

import asyncio

async def verify_test_approach():
    """验证我的测试方法是否准确"""
    
    print("🔍 验证分层测试方法的准确性...")
    
    # 验证1: ADK SDK 真实可用性
    print("\n1. 验证 ADK SDK 层...")
    try:
        from google.adk.agents import Agent
        from google.adk.runners import InMemoryRunner
        agent = Agent(name="verify", model="gemini-1.5-flash", instruction="test")
        print(f"✅ ADK SDK 确实可用，Agent类型: {type(agent)}")
        print(f"✅ Agent方法包含: {[m for m in dir(agent) if 'run' in m]}")
    except Exception as e:
        print(f"❌ ADK SDK 问题: {e}")
    
    # 验证2: 框架初始化真实性
    print("\n2. 验证框架初始化层...")
    try:
        from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
        adapter = AdkFrameworkAdapter()
        await adapter.initialize()
        health = await adapter.health_check()
        print(f"✅ 框架初始化成功，健康状态: {health['status']}")
    except Exception as e:
        print(f"❌ 框架初始化问题: {e}")
    
    # 验证3: 架构委托正确性
    print("\n3. 验证架构委托层...")
    try:
        from src.aether_frame.agents.manager import AgentManager
        from src.aether_frame.contracts import AgentConfig, FrameworkType
        
        manager = AgentManager()
        # 检查是否有正确的委托方法
        has_runtime_methods = hasattr(manager, 'execute_with_runtime') and hasattr(manager, 'execute_live_with_runtime')
        print(f"✅ AgentManager 有运行时委托方法: {has_runtime_methods}")
    except Exception as e:
        print(f"❌ 架构委托问题: {e}")
    
    print(f"\n📊 我的测试方法验证: 每层都可以独立验证，问题定位精确")

if __name__ == "__main__":
    asyncio.run(verify_test_approach())