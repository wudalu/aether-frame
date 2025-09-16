#!/usr/bin/env python3
"""
Deep debug version to trace exact code execution path.
Hooks into all key methods to see what's actually called.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

def trace_method_calls():
    """Hook into key methods to trace actual execution path."""
    original_methods = {}
    
    # Hook ADK Framework Adapter
    try:
        from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
        
        # Hook execute_task
        original_methods['adapter_execute'] = AdkFrameworkAdapter.execute_task
        async def traced_adapter_execute(self, task_request, strategy):
            print(f"\n🔥 ADK_ADAPTER.execute_task() CALLED")
            print(f"   Task ID: {task_request.task_id}")
            print(f"   Strategy Framework: {strategy.framework_type}")
            
            result = await original_methods['adapter_execute'](self, task_request, strategy)
            
            print(f"🔥 ADK_ADAPTER.execute_task() RETURNING")
            print(f"   Result Status: {result.status}")
            print(f"   Result Messages: {len(result.messages) if result.messages else 0}")
            
            return result
        AdkFrameworkAdapter.execute_task = traced_adapter_execute
        
        # Hook session agent creation
        original_methods['get_or_create_agent'] = AdkFrameworkAdapter._get_or_create_session_agent
        async def traced_get_or_create_agent(self, session_id, task_request, strategy):
            print(f"\n🏭 ADK_ADAPTER._get_or_create_session_agent() CALLED")
            print(f"   Session ID: {session_id}")
            
            agent = await original_methods['get_or_create_agent'](self, session_id, task_request, strategy)
            
            print(f"🏭 ADK_ADAPTER._get_or_create_session_agent() RETURNING")
            print(f"   Agent ID: {agent.agent_id}")
            print(f"   Agent Type: {type(agent).__name__}")
            
            return agent
        AdkFrameworkAdapter._get_or_create_session_agent = traced_get_or_create_agent
        
    except ImportError as e:
        print(f"Could not hook ADK Adapter: {e}")
    
    # Hook ADK Domain Agent
    try:
        from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
        
        # Hook initialize
        original_methods['domain_init'] = AdkDomainAgent.initialize
        async def traced_domain_init(self):
            print(f"\n🤖 ADK_DOMAIN_AGENT.initialize() CALLED")
            print(f"   Agent ID: {self.agent_id}")
            
            await original_methods['domain_init'](self)
            
            print(f"🤖 ADK_DOMAIN_AGENT.initialize() COMPLETED")
            print(f"   ADK Agent Created: {self.adk_agent is not None}")
            
        AdkDomainAgent.initialize = traced_domain_init
        
        # Hook execute 
        original_methods['domain_execute'] = AdkDomainAgent.execute
        async def traced_domain_execute(self, agent_request):
            print(f"\n⚡ ADK_DOMAIN_AGENT.execute() CALLED")
            print(f"   Agent Request Task ID: {agent_request.task_request.task_id}")
            print(f"   Agent Request Type: {agent_request.agent_type}")
            
            result = await original_methods['domain_execute'](self, agent_request)
            
            print(f"⚡ ADK_DOMAIN_AGENT.execute() RETURNING")
            print(f"   Task Result Status: {result.status}")
            print(f"   Response Length: {len(result.messages[0].content) if result.messages else 0}")
            
            return result
        AdkDomainAgent.execute = traced_domain_execute
        
        # Hook _execute_with_adk_runner
        original_methods['adk_runner'] = AdkDomainAgent._execute_with_adk_runner
        async def traced_adk_runner(self, agent_request):
            print(f"\n🚀 ADK_DOMAIN_AGENT._execute_with_adk_runner() CALLED")
            print(f"   Runtime Context Keys: {list(self.runtime_context.keys())}")
            print(f"   Has Runner: {'runner' in self.runtime_context}")
            print(f"   Has Session ID: {'session_id' in self.runtime_context}")
            
            result = await original_methods['adk_runner'](self, agent_request)
            
            print(f"🚀 ADK_DOMAIN_AGENT._execute_with_adk_runner() RETURNING")
            print(f"   Result: {type(result).__name__}")
            
            return result
        AdkDomainAgent._execute_with_adk_runner = traced_adk_runner
        
        # Hook _run_adk_with_runner
        original_methods['run_adk'] = AdkDomainAgent._run_adk_with_runner
        async def traced_run_adk(self, runner, user_id, session_id, adk_content):
            print(f"\n🎯 ADK_DOMAIN_AGENT._run_adk_with_runner() CALLED")
            print(f"   User ID: {user_id}")
            print(f"   Session ID: {session_id}")
            print(f"   Content: {adk_content[:50]}...")
            print(f"   Runner Type: {type(runner).__name__}")
            
            response = await original_methods['run_adk'](self, runner, user_id, session_id, adk_content)
            
            print(f"🎯 ADK_DOMAIN_AGENT._run_adk_with_runner() RETURNING")
            print(f"   Response: {response[:100]}..." if response else "None")
            
            return response
        AdkDomainAgent._run_adk_with_runner = traced_run_adk
        
    except ImportError as e:
        print(f"Could not hook ADK Domain Agent: {e}")
    
    return original_methods

async def deep_trace_execution():
    """Run execution with deep method tracing."""
    print("🔍 DEEP EXECUTION TRACE - HOOKING INTO ALL METHODS")
    print("="*80)
    
    # Install method hooks
    original_methods = trace_method_calls()
    
    try:
        # Create task request
        task_request = TaskRequest(
            task_id="deep_trace_test",
            task_type="chat",
            description="Deep trace execution path",
            messages=[
                UniversalMessage(
                    role="user", 
                    content="What is your name?",
                    metadata={"trace": "deep"}
                )
            ],
            metadata={
                "preferred_model": "deepseek-chat",
                "framework": "adk",
                "trace_mode": "deep"
            }
        )
        
        print(f"\n📋 TASK REQUEST CREATED")
        print(f"   Task ID: {task_request.task_id}")
        print(f"   Messages: {len(task_request.messages)}")
        
        # Initialize system
        print(f"\n🚀 INITIALIZING SYSTEM...")
        settings = Settings()
        assistant = await create_ai_assistant(settings)
        print(f"✅ System initialized")
        
        # Execute with full tracing
        print(f"\n⚡ STARTING EXECUTION...")
        start_time = datetime.now()
        
        result = await assistant.process_request(task_request)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        print(f"\n📊 EXECUTION COMPLETED")
        print(f"   Time: {execution_time:.2f}s")
        print(f"   Status: {result.status}")
        print(f"   Framework: {result.metadata.get('framework')}")
        print(f"   Session ID: {result.metadata.get('session_id')}")
        
        if result.messages:
            print(f"   Response: {result.messages[0].content[:100]}...")
        
        return True
        
    finally:
        # Restore original methods
        try:
            from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
            if 'adapter_execute' in original_methods:
                AdkFrameworkAdapter.execute_task = original_methods['adapter_execute']
            if 'get_or_create_agent' in original_methods:
                AdkFrameworkAdapter._get_or_create_session_agent = original_methods['get_or_create_agent']
        except:
            pass
            
        try:
            from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
            if 'domain_init' in original_methods:
                AdkDomainAgent.initialize = original_methods['domain_init']
            if 'domain_execute' in original_methods:
                AdkDomainAgent.execute = original_methods['domain_execute']
            if 'adk_runner' in original_methods:
                AdkDomainAgent._execute_with_adk_runner = original_methods['adk_runner']
            if 'run_adk' in original_methods:
                AdkDomainAgent._run_adk_with_runner = original_methods['run_adk']
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(deep_trace_execution())
    
    if success:
        print("\n🎉 DEEP TRACE COMPLETED!")
    else:
        print("\n💥 DEEP TRACE FAILED!")
        sys.exit(1)