#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整ADK参数传递验证测试 - 验证从请求到ADK Agent的完整参数传递"""

import asyncio
import uuid
from datetime import datetime

from src.aether_frame.contracts import (
    AgentConfig,
    AgentRequest,
    ExecutionContext,
    FrameworkType,
    TaskRequest,
    UniversalMessage,
    UserContext,
)


async def test_adk_pure_flow():
    """测试纯ADK流程 - 验证ADK本身的工作方式"""
    print("🧪 纯ADK流程测试")
    print("=" * 40)

    try:
        from google.adk.agents import Agent
        from google.adk.artifacts import InMemoryArtifactService
        from google.adk.runners import InMemoryRunner, Runner
        from google.adk.sessions import InMemorySessionService

        print("✅ ADK组件导入成功")

        # Step 1: 创建ADK Agent
        agent = Agent(
            name="pure_test_agent",
            model="gemini-1.5-flash",
            instruction="You are a helpful assistant. Respond to user messages clearly.",
        )
        print("✅ ADK Agent创建成功")

        # Step 2: 创建Runner
        session_service = InMemorySessionService()
        artifact_service = InMemoryArtifactService()

        runner = Runner(
            app_name="pure_adk_test",
            agent=agent,
            session_service=session_service,
            artifact_service=artifact_service,
        )
        print("✅ ADK Runner创建成功")

        # Step 3: 创建Session
        session = await session_service.create_session(
            app_name="pure_adk_test", user_id="test_user"
        )
        print("✅ ADK Session创建成功")

        # Step 4: 测试ADK Agent直接执行
        print("\n🎯 测试ADK Agent直接执行...")

        # 检查Agent的run_async参数
        import inspect

        print(f"Agent.run_async签名: {inspect.signature(agent.run_async)}")

        # 需要InvocationContext
        from google.adk.runners import InvocationContext

        # 创建InvocationContext
        context = InvocationContext(session=session)

        print("✅ InvocationContext创建成功")

        # 执行Agent
        print("🚀 执行Agent.run_async...")

        # run_async返回AsyncGenerator[Event, None]
        event_count = 0
        async for event in agent.run_async(context):
            event_count += 1
            print(f"📦 事件 {event_count}: {type(event).__name__}")
            print(f"    内容: {str(event)[:100]}...")

            # 限制事件数量避免无限循环
            if event_count >= 5:
                break

        print(f"✅ 收到 {event_count} 个ADK事件")

        return True

    except Exception as e:
        print(f"❌ 纯ADK流程失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_our_adk_integration():
    """测试我们的ADK集成 - 验证我们的参数传递是否正确"""
    print("\n🔗 测试我们的ADK集成")
    print("=" * 40)

    # 创建任务请求
    task = TaskRequest(
        task_id=f"integration_{uuid.uuid4().hex[:6]}",
        task_type="chat",
        description="integration test",
        messages=[UniversalMessage(role="user", content="Hello, how are you?")],
        user_context=UserContext(user_id="integration_test"),
    )

    try:
        # Step 1: 创建正确的AdkDomainAgent
        print("🤖 创建AdkDomainAgent...")
        from src.aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent

        # 创建Agent配置
        agent_config = {
            "agent_type": "conversational_agent",
            "model_config": {"model": "gemini-1.5-flash", "temperature": 0.7},
            "system_prompt": "You are a helpful assistant.",
            "framework_type": FrameworkType.ADK,
        }

        domain_agent = AdkDomainAgent(
            agent_id="integration_test_agent", config=agent_config
        )

        await domain_agent.initialize()
        print("✅ AdkDomainAgent初始化成功")
        print(f"✅ 使用真实ADK: {domain_agent.adk_agent is not None}")

        # Step 2: 创建AgentRequest
        print("\n📝 创建AgentRequest...")
        agent_request = AgentRequest(
            agent_config=AgentConfig(
                framework_type=FrameworkType.ADK,
                agent_type="conversational_agent",
                model_config=agent_config["model_config"],
                system_prompt=agent_config["system_prompt"],
            ),
            task_request=task,
            agent_type="conversational_agent",
            metadata={"test": "integration"},
        )

        # Step 3: 直接执行Domain Agent
        print("\n⚙️ 执行AdkDomainAgent...")
        result = await domain_agent.execute(agent_request)

        print(f"✅ 执行状态: {result.status}")
        if result.error_message:
            print(f"❌ 错误: {result.error_message}")
        if result.messages:
            print(f"✅ 响应消息数量: {len(result.messages)}")
            print(f"✅ 第一个消息: {result.messages[0].content[:100]}...")

        return result.status.value == "success"

    except Exception as e:
        print(f"❌ ADK集成测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_parameter_validation():
    """验证我们传递给ADK的参数格式是否正确"""
    print("\n🔍 参数验证测试")
    print("=" * 40)

    try:
        # 验证我们的消息转换逻辑
        from src.aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent

        domain_agent = AdkDomainAgent("param_test", {})

        # 测试消息转换
        messages = [
            UniversalMessage(role="user", content="Hello"),
            UniversalMessage(role="assistant", content="Hi there!"),
            UniversalMessage(role="user", content="How are you?"),
        ]

        adk_input = domain_agent._convert_messages_for_adk(messages)
        print(f"✅ 消息转换结果: {adk_input}")

        # 验证消息格式是否是ADK期望的
        print(f"✅ 转换后类型: {type(adk_input)}")
        print(f"✅ 内容长度: {len(adk_input) if isinstance(adk_input, str) else 'N/A'}")

        return True

    except Exception as e:
        print(f"❌ 参数验证失败: {e}")
        return False


async def test_complete_end_to_end_flow():
    """测试完整的端到端流程"""
    print("\n🎯 完整端到端流程测试")
    print("=" * 40)

    try:
        from src.aether_frame.config.settings import Settings
        from src.aether_frame.execution.ai_assistant import AIAssistant

        # 创建简单任务
        task = TaskRequest(
            task_id=f"e2e_{uuid.uuid4().hex[:6]}",
            task_type="chat",
            description="end to end test",
            messages=[UniversalMessage(role="user", content="Say hello")],
            user_context=UserContext(user_id="e2e_test"),
        )

        print(f"📝 任务: {task.task_id}")

        # 执行完整流程
        assistant = AIAssistant(Settings())
        result = await assistant.process_request(task)

        print(f"✅ 执行状态: {result.status}")
        if result.error_message:
            print(f"❌ 错误: {result.error_message}")
        else:
            print("✅ 端到端流程执行成功")

        return result.status.value == "success"

    except Exception as e:
        print(f"❌ 端到端流程失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """主测试流程"""
    print("🚀 完整ADK参数传递验证测试")
    print("=" * 60)

    test_results = []

    # Test 1: 纯ADK流程
    result1 = await test_adk_pure_flow()
    test_results.append(("纯ADK流程", result1))

    # Test 2: 我们的集成
    result2 = await test_our_adk_integration()
    test_results.append(("ADK集成", result2))

    # Test 3: 参数验证
    result3 = await test_parameter_validation()
    test_results.append(("参数验证", result3))

    # Test 4: 完整端到端
    result4 = await test_complete_end_to_end_flow()
    test_results.append(("完整端到端", result4))

    # 结果汇总
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} {test_name}")
        if result:
            passed += 1

    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")

    if passed == total:
        print("🎉 所有测试通过！ADK参数传递正确。")
    else:
        print("⚠️ 部分测试失败，需要修复ADK参数传递问题。")

    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
