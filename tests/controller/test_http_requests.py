#!/usr/bin/env python3
"""
简单的HTTP请求测试脚本

这个脚本向Controller API发送HTTP请求来测试连通性和基本功能。
支持多个提示词选择和接口选择功能。
"""

import requests
import json
import time
import argparse
import sys


# 预定义的提示词配置
SYSTEM_PROMPTS = {
    "echarts": """你是一个专业的ECharts图表生成器。无论用户输入什么内容，你都必须严格按照以下格式输出：

1. 只输出一个完整的ECharts option配置对象
2. 必须用```echarts 代码块包裹
3. 不输出任何解释、说明或其他文字
4. 配置必须是有效的JavaScript对象格式
5. 根据用户输入的内容类型和数据，智能选择合适的图表类型（柱状图、折线图、饼图、散点图等）

输出格式示例：
```echarts
{
  title: {
    text: '图表标题'
  },
  xAxis: {
    type: 'category',
    data: ['数据1', '数据2', '数据3']
  },
  yAxis: {
    type: 'value'
  },
  series: [{
    data: [120, 200, 150],
    type: 'bar'
  }]
}
```

记住：无论输入什么，都只输出被```echarts包裹的option配置，不要有任何其他内容。""",

    "default": "你是一个有用的AI助手，请根据用户的问题提供准确和有帮助的回答。",

    "analytical": "你是一个专业的数据分析师，擅长分析数据、生成图表和提供洞察。请用专业的语言回答用户的问题。",

    "creative": "你是一个富有创意的助手，善于提供创新的想法和解决方案。请用生动有趣的方式回答用户的问题。"
}


def get_system_prompt(prompt_key):
    """获取指定的系统提示词"""
    return SYSTEM_PROMPTS.get(prompt_key, SYSTEM_PROMPTS["default"])


def test_health_endpoint():
    """测试健康检查端点"""
    print("=" * 50)
    print("测试健康检查端点")
    print("=" * 50)

    url = "http://localhost:8000/api/v1/health"

    try:
        response = requests.get(url, timeout=10)
        print(f"请求URL: {url}")
        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print(
            f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"请求失败: {e}")
        return False


def test_detailed_health_endpoint():
    """测试详细健康检查端点"""
    print("\n" + "=" * 50)
    print("测试详细健康检查端点")
    print("=" * 50)

    url = "http://localhost:8000/api/v1/health/detailed"

    try:
        response = requests.get(url, timeout=10)
        print(f"请求URL: {url}")
        print(f"响应状态码: {response.status_code}")
        print(
            f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"请求失败: {e}")
        return False


def test_chat_endpoint():
    """测试聊天端点（需要先创建context）"""
    print("\n" + "=" * 50)
    print("测试聊天端点（需要先创建context）")
    print("=" * 50)

    # 第一步：创建context
    context_url = "http://localhost:8000/api/v1/create-context"
    context_data = {
        "agent_type": "chat_assistant",
        "system_prompt": "你是一个友好的聊天助手",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 1500
    }

    try:
        print("第一步：创建context")
        print(f"请求URL: {context_url}")
        print(f"请求数据: {json.dumps(context_data, indent=2, ensure_ascii=False)}")

        context_response = requests.post(
            context_url,
            json=context_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if context_response.status_code != 200:
            print(f"创建context失败: {context_response.status_code}")
            return False

        context_result = context_response.json()
        agent_id = context_result["agent_id"]
        session_id = context_result["session_id"]

        print(f"Context创建成功: agent_id={agent_id}, session_id={session_id}")

        # 第二步：使用chat接口
        chat_url = "http://localhost:8000/api/v1/chat"
        chat_data = {
            "message": "你好，这是一个测试消息",
            "agent_id": agent_id,
            "session_id": session_id,
            "metadata": {"test": "chat_endpoint"}
        }

        print("\n第二步：调用chat接口")
        print(f"请求URL: {chat_url}")
        print(f"请求数据: {json.dumps(chat_data, indent=2, ensure_ascii=False)}")

        chat_response = requests.post(
            chat_url,
            json=chat_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"响应状态码: {chat_response.status_code}")
        print(f"响应头: {dict(chat_response.headers)}")
        print(
            f"响应内容: {json.dumps(chat_response.json(), indent=2, ensure_ascii=False)}")

        return chat_response.status_code == 200

    except Exception as e:
        print(f"请求失败: {e}")
        return False


def test_process_endpoint(system_prompt_key="default"):
    """测试处理端点"""
    print("\n" + "=" * 50)
    print(f"测试处理端点 (使用提示词: {system_prompt_key})")
    print("=" * 50)

    url = "http://localhost:8000/api/v1/process"

    # 测试数据
    test_data = {
        "task_type": "analysis",
        "description": "分析测试任务",
        "messages": [
            {
                "role": "user",
                "content": "给我一个简单的饼图",
                "metadata": {"source": "test"}
            }
        ],
        "model": "deepseek-chat",
        "temperature": 0.5,
        "max_tokens": 2000,
        "agent_type": "analytical_assistant",
        "system_prompt": get_system_prompt(system_prompt_key),
        "available_tools": ["calculator"],
        "metadata": {"priority": "normal"}
    }

    try:
        print(f"请求URL: {url}")
        print(f"使用的系统提示词: {system_prompt_key}")
        print(f"请求数据: {json.dumps(test_data, indent=2, ensure_ascii=False)}")

        response = requests.post(
            url,
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print(
            f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"请求失败: {e}")
        return False


def test_create_context_endpoint():
    """测试创建RuntimeContext端点"""
    print("\n" + "=" * 50)
    print("测试创建RuntimeContext端点")
    print("=" * 50)

    url = "http://localhost:8000/api/v1/create-context"

    # 测试数据 - 使用 echarts 提示词配置
    test_data = {
        "agent_type": "echarts_generator",
        "system_prompt": get_system_prompt("echarts"),
        "model": "deepseek-chat",
        "temperature": 0.3,  # 降低温度以获得更一致的输出
        "max_tokens": 2000,
        "available_tools": [],
        "user_id": "test_user_echarts",
        "framework_config": {
            "provider": "deepseek"
        },
        "metadata": {
            "purpose": "echarts_testing",
            "chart_type": "specialized",
            "priority": "high"
        }
    }

    try:
        print(f"请求URL: {url}")
        print(f"请求数据: {json.dumps(test_data, indent=2, ensure_ascii=False)}")

        response = requests.post(
            url,
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        response_data = response.json()
        print(
            f"响应内容: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

        # 如果成功，返回创建的context信息用于后续测试
        if response.status_code == 200:
            return response_data
        return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None


def test_chat_with_context(context_info):
    """测试使用预创建的RuntimeContext进行聊天"""
    if not context_info:
        print("跳过测试：没有可用的context信息")
        return False

    print("\n" + "=" * 50)
    print("测试使用预创建RuntimeContext的聊天端点 - ECharts饼图生成")
    print("=" * 50)

    url = "http://localhost:8000/api/v1/chat"

    # 使用预创建的context信息进行聊天
    test_data = {
        "message": "帮我生成一个饼图，显示公司各部门的人员分布：技术部40人，销售部30人，市场部20人，行政部10人",
        "agent_id": context_info["agent_id"],
        "session_id": context_info["session_id"],
        "metadata": {
            "chart_request": True,
            "expected_output": "echarts_config",
            "original_context_creation_time": context_info.get("created_at")
        }
    }

    try:
        print(f"请求URL: {url}")
        print(f"使用的agent_id: {context_info['agent_id']}")
        print(f"使用的session_id: {context_info['session_id']}")
        print(f"请求数据: {json.dumps(test_data, indent=2, ensure_ascii=False)}")

        response = requests.post(
            url,
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        response_data = response.json()
        print(
            f"响应内容: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

        # 检查是否包含 ECharts 配置
        if response.status_code == 200 and "```echarts" in response_data.get("message", ""):
            print("\n🎉 检测到 ECharts 配置输出！")
            print("=" * 50)
            # 提取并显示 ECharts 配置
            content = response_data["message"]
            start_idx = content.find("```echarts")
            end_idx = content.find("```", start_idx + 10)
            if start_idx != -1 and end_idx != -1:
                echarts_config = content[start_idx + 10:end_idx].strip()
                print("ECharts 配置:")
                print(echarts_config)
                print("=" * 50)

        return response.status_code == 200
    except Exception as e:
        print(f"请求失败: {e}")
        return False


def test_invalid_requests():
    """测试无效请求"""
    print("\n" + "=" * 50)
    print("测试无效请求")
    print("=" * 50)

    # 测试不存在的端点
    print("1. 测试不存在的端点")
    try:
        response = requests.get(
            "http://localhost:8000/api/v1/nonexistent", timeout=10)
        print(f"不存在端点响应状态码: {response.status_code}")
    except Exception as e:
        print(f"请求失败: {e}")

    # 测试错误的HTTP方法
    print("\n2. 测试错误的HTTP方法")
    try:
        response = requests.get(
            "http://localhost:8000/api/v1/chat", timeout=10)
        print(f"错误方法响应状态码: {response.status_code}")
    except Exception as e:
        print(f"请求失败: {e}")

    # 测试无效的JSON数据
    print("\n3. 测试chat接口缺少必需字段")
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/chat",
            json={"message": "测试"},  # 缺少必需的agent_id和session_id字段
            timeout=10
        )
        print(f"无效数据响应状态码: {response.status_code}")
        print(
            f"错误响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"请求失败: {e}")

    # 测试process接口缺少必需字段
    print("\n4. 测试process接口缺少必需字段")
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/process",
            json={"task_type": "test"},  # 缺少必需的messages字段
            timeout=10
        )
        print(f"无效数据响应状态码: {response.status_code}")
        print(
            f"错误响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"请求失败: {e}")

    # 无效请求测试总是返回True，因为我们期望这些请求失败
    return True


def interactive_mode():
    """交互式模式，让用户选择测试选项"""
    print("Controller API HTTP请求测试 - 交互模式")
    print("=" * 60)

    # 选择测试接口
    print("\n可用的测试接口:")
    test_options = {
        "1": ("健康检查", test_health_endpoint),
        "2": ("详细健康检查", test_detailed_health_endpoint),
        "3": ("聊天端点", test_chat_endpoint),
        "4": ("处理端点", test_process_endpoint),
        "5": ("创建RuntimeContext", test_create_context_endpoint),
        "6": ("Context完整流程测试 (ECharts)", None),  # 特殊处理
        "7": ("无效请求测试", test_invalid_requests),
        "all": ("所有测试", None)
    }

    for key, (name, _) in test_options.items():
        print(f"  {key}: {name}")

    selected_test = input("\n请选择要运行的测试 (输入数字或'all'): ").strip()

    # 如果选择处理端点，让用户选择提示词
    system_prompt_key = "default"
    if selected_test == "4" or selected_test == "all":
        print("\n可用的系统提示词:")
        for key, prompt in SYSTEM_PROMPTS.items():
            preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
            print(f"  {key}: {preview}")

        prompt_choice = input(f"\n请选择系统提示词 (默认: default): ").strip()
        if prompt_choice in SYSTEM_PROMPTS:
            system_prompt_key = prompt_choice

    return selected_test, system_prompt_key


def run_selected_tests(selected_test, system_prompt_key):
    """运行选定的测试"""
    print("\n" + "=" * 60)
    print("注意: 请确保服务器在 http://localhost:8000 上运行")
    print("启动服务器命令: python -m aether_frame.controller.server")
    print("=" * 60)

    start_time = time.time()
    results = []

    test_options = {
        "1": ("健康检查", test_health_endpoint),
        "2": ("详细健康检查", test_detailed_health_endpoint),
        "3": ("聊天端点", test_chat_endpoint),
        "4": ("处理端点", lambda: test_process_endpoint(system_prompt_key)),
        "5": ("创建RuntimeContext", test_create_context_endpoint),
        "7": ("无效请求测试", test_invalid_requests),
    }

    if selected_test == "all":
        # 运行所有测试
        for key in ["1", "2", "3", "4", "5"]:
            test_name, test_func = test_options[key]
            print(f"\n正在运行: {test_name}")
            success = test_func()
            results.append((test_name, success))
            time.sleep(1)

        # 运行Context完整流程测试
        print(f"\n正在运行: Context完整流程测试")
        context_info = test_create_context_endpoint()
        if context_info:
            success = test_chat_with_context(context_info)
            results.append(("Context完整流程测试", success))
        else:
            results.append(("Context完整流程测试", False))
        time.sleep(1)

        # 运行无效请求测试
        test_invalid_requests()

    elif selected_test == "6":
        # Context完整流程测试
        print(f"\n正在运行: Context完整流程测试")
        context_info = test_create_context_endpoint()
        if context_info:
            success = test_chat_with_context(context_info)
            results.append(("Context完整流程测试", success))
        else:
            results.append(("Context完整流程测试", False))
    elif selected_test in test_options:
        test_name, test_func = test_options[selected_test]
        print(f"\n正在运行: {test_name}")
        success = test_func()
        results.append((test_name, success))
    else:
        print("无效的选择！")
        return

    # 总结结果
    if results:
        end_time = time.time()
        print("\n" + "=" * 60)
        print("测试结果总结")
        print("=" * 60)

        for test_name, success in results:
            status = "✅ 成功" if success else "❌ 失败"
            print(f"{test_name}: {status}")

        print(f"\n总测试时间: {end_time - start_time:.2f} 秒")

        successful_tests = sum(1 for _, success in results if success)
        print(f"成功测试: {successful_tests}/{len(results)}")

        if successful_tests == len(results):
            print("\n🎉 所有测试都成功了！API连通性正常。")
        else:
            print(f"\n⚠️  有 {len(results) - successful_tests} 个测试失败。")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Controller API HTTP请求测试工具")
    parser.add_argument("--test", "-t", choices=["1", "2", "3", "4", "5", "6", "7", "all"],
                        help="指定要运行的测试 (1:健康检查, 2:详细健康检查, 3:聊天端点, 4:处理端点, 5:创建Context, 6:Context完整流程, 7:无效请求, all:所有测试)")
    parser.add_argument("--prompt", "-p", choices=list(SYSTEM_PROMPTS.keys()),
                        default="default", help="指定系统提示词")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="启用交互模式")

    args = parser.parse_args()

    if args.interactive or (not args.test):
        # 交互模式
        selected_test, system_prompt_key = interactive_mode()
        run_selected_tests(selected_test, system_prompt_key)
    else:
        # 命令行模式
        run_selected_tests(args.test, args.prompt)


if __name__ == "__main__":
    main()
