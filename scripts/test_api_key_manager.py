#!/usr/bin/env python3
"""
测试API Key管理器的脚本
"""

import asyncio
import sys
import os

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aether_frame.config.settings import Settings
from aether_frame.services import initialize_api_key_manager


async def test_api_key_manager():
    """测试API key管理器"""
    print("🔧 测试API Key管理器...")
    
    # 创建设置
    settings = Settings()
    print(f"✅ 设置创建成功")
    print(f"   - API Key管理器启用: {settings.enable_api_key_manager}")
    print(f"   - 刷新间隔: {settings.api_key_refresh_interval}秒")
    print(f"   - 数据库主机: {settings.postgres_host}")
    print(f"   - 数据库端口: {settings.postgres_port}")
    print(f"   - 数据库名称: {settings.postgres_database}")
    
    if not settings.enable_api_key_manager:
        print("⚠️  API Key管理器已禁用，跳过测试")
        return
    
    # 初始化API key管理器
    try:
        manager = initialize_api_key_manager(settings)
        print("✅ API Key管理器初始化成功")
        
        # 尝试启动管理器（这可能会失败如果数据库不可用）
        try:
            await manager.start()
            print("✅ API Key管理器启动成功")
            
            # 测试设置查询
            manager.set_query("azure_openai", "SELECT 'test-azure-key' as api_key")
            manager.set_query("openai", "SELECT 'test-openai-key' as api_key")
            print("✅ 查询设置成功")
            
            # 等待一次刷新
            print("⏳ 等待API key刷新...")
            await asyncio.sleep(2)
            
            # 检查keys
            azure_key = manager.get_azure_api_key()
            openai_key = manager.get_openai_api_key()
            
            print(f"🔑 Azure API Key: {azure_key[:10] + '...' if azure_key else 'None'}")
            print(f"🔑 OpenAI API Key: {openai_key[:10] + '...' if openai_key else 'None'}")
            
            # 停止管理器
            await manager.stop()
            print("✅ API Key管理器停止成功")
            
        except Exception as e:
            print(f"⚠️  API Key管理器启动失败（可能是数据库连接问题）: {e}")
            print("💡 这是正常的，如果你还没有配置数据库")
            
    except Exception as e:
        print(f"❌ API Key管理器初始化失败: {e}")
        return
    
    # 测试Settings类的API key获取方法
    print("\n🔧 测试Settings API key获取方法...")
    
    azure_key = settings.get_azure_api_key()
    openai_key = settings.get_openai_api_key()
    anthropic_key = settings.get_anthropic_api_key()
    
    print(f"🔑 Azure API Key (从Settings): {azure_key[:10] + '...' if azure_key else 'None'}")
    print(f"🔑 OpenAI API Key (从Settings): {openai_key[:10] + '...' if openai_key else 'None'}")
    print(f"🔑 Anthropic API Key (从Settings): {anthropic_key[:10] + '...' if anthropic_key else 'None'}")
    
    print("\n✅ 测试完成！")


if __name__ == "__main__":
    asyncio.run(test_api_key_manager())