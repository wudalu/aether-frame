#!/usr/bin/env python3
"""
Trace actual execution inside AdkDomainAgent with runtime logging.
Shows what really happens when code runs.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

def inject_runtime_logging():
    """Inject logging into AdkDomainAgent methods to see real execution."""
    
    # Hook AdkDomainAgent methods
    from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
    
    # Store original methods
    original_execute = AdkDomainAgent.execute
    original_execute_with_adk = AdkDomainAgent._execute_with_adk_runner
    original_run_adk = AdkDomainAgent._run_adk_with_runner
    original_convert_messages = AdkDomainAgent._convert_messages_to_adk_content
    original_convert_response = AdkDomainAgent._convert_adk_response_to_task_result
    
    async def logged_execute(self, agent_request):
        print(f"\n🤖 === ADK_DOMAIN_AGENT.execute() START ===")
        print(f"   Agent ID: {self.agent_id}")
        print(f"   Task ID: {agent_request.task_request.task_id}")
        print(f"   Task Type: {agent_request.task_request.task_type}")
        print(f"   Messages Count: {len(agent_request.task_request.messages)}")
        print(f"   Runtime Context Keys: {list(self.runtime_context.keys())}")
        
        start_time = datetime.now()
        result = await original_execute(self, agent_request)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        print(f"🤖 === ADK_DOMAIN_AGENT.execute() END ===")
        print(f"   Execution Time: {execution_time:.2f}s")
        print(f"   Result Status: {result.status}")
        print(f"   Result Messages: {len(result.messages) if result.messages else 0}")
        
        return result
    
    async def logged_execute_with_adk(self, agent_request):
        print(f"\n🚀 === _execute_with_adk_runner() START ===")
        task_request = agent_request.task_request
        
        print(f"   Task Messages: {[msg.content for msg in task_request.messages]}")
        
        # Check runtime context
        runner = self.runtime_context.get("runner")
        user_id = self.runtime_context.get("user_id", "anonymous")  
        session_id = self.runtime_context.get("session_id")
        
        print(f"   Runner Available: {runner is not None}")
        print(f"   Runner Type: {type(runner).__name__ if runner else 'None'}")
        print(f"   User ID: {user_id}")
        print(f"   Session ID: {session_id}")
        
        result = await original_execute_with_adk(self, agent_request)
        
        print(f"🚀 === _execute_with_adk_runner() END ===")
        print(f"   Final Result: {type(result).__name__}")
        
        return result
    
    async def logged_run_adk(self, runner, user_id, session_id, adk_content):
        print(f"\n🎯 === _run_adk_with_runner() START ===")
        print(f"   Input Content: '{adk_content[:100]}...'" if len(adk_content) > 100 else f"   Input Content: '{adk_content}'")
        print(f"   User ID: {user_id}")
        print(f"   Session ID: {session_id}")
        print(f"   Runner: {type(runner).__name__}")
        
        try:
            print(f"   🔍 Attempting ADK imports...")
            from google.genai import types
            print(f"   ✅ ADK types imported successfully")
            
            print(f"   🔨 Creating ADK Content...")
            content = types.Content(role="user", parts=[types.Part(text=adk_content)])
            print(f"   ✅ ADK Content created: {content}")
            
            print(f"   ⚡ Calling runner.run_async()...")
            events = runner.run_async(
                user_id=user_id, 
                session_id=session_id, 
                new_message=content
            )
            print(f"   ✅ runner.run_async() returned: {type(events)}")
            
            print(f"   🔄 Processing events...")
            final_response = None
            event_count = 0
            
            async for event in events:
                event_count += 1
                print(f"   📦 Event {event_count}: {type(event).__name__}")
                print(f"      Event Details: {event}")
                
                if hasattr(event, 'is_final_response') and event.is_final_response():
                    print(f"      🎯 FINAL RESPONSE EVENT DETECTED!")
                    if hasattr(event, 'content') and event.content:
                        if hasattr(event.content, 'parts') and event.content.parts:
                            final_response = event.content.parts[0].text.strip()
                            print(f"      📝 Extracted Response: '{final_response[:100]}...'" if len(final_response) > 100 else f"      📝 Extracted Response: '{final_response}'")
                            break
                
                # Limit event processing to avoid infinite loops
                if event_count >= 50:
                    print(f"      ⚠️ Stopping after {event_count} events")
                    break
            
            result = final_response or "No response from ADK"
            print(f"   ✅ Final Result: '{result[:100]}...'" if len(result) > 100 else f"   ✅ Final Result: '{result}'")
            
        except ImportError as e:
            print(f"   ⚠️ ImportError - falling back to mock: {e}")
            result = f"Mock ADK processed: {adk_content}"
            
        except Exception as e:
            print(f"   ❌ Exception during ADK execution: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"ADK Runner execution failed: {str(e)}")
        
        print(f"🎯 === _run_adk_with_runner() END ===")
        return result
    
    def logged_convert_messages(self, messages):
        print(f"\n🔄 === _convert_messages_to_adk_content() START ===")
        print(f"   Input Messages: {len(messages)}")
        for i, msg in enumerate(messages):
            print(f"      Message {i}: role='{msg.role}', content='{msg.content[:50]}...'" if len(msg.content) > 50 else f"      Message {i}: role='{msg.role}', content='{msg.content}'")
        
        result = original_convert_messages(self, messages)
        
        print(f"   Converted Content: '{result[:100]}...'" if len(result) > 100 else f"   Converted Content: '{result}'")
        print(f"🔄 === _convert_messages_to_adk_content() END ===")
        
        return result
    
    def logged_convert_response(self, adk_response, task_id):
        print(f"\n📤 === _convert_adk_response_to_task_result() START ===")
        print(f"   ADK Response: '{adk_response[:100]}...'" if len(str(adk_response)) > 100 else f"   ADK Response: '{adk_response}'")
        print(f"   Task ID: {task_id}")
        
        result = original_convert_response(self, adk_response, task_id)
        
        print(f"   TaskResult Status: {result.status}")
        print(f"   TaskResult Messages: {len(result.messages) if result.messages else 0}")
        print(f"📤 === _convert_adk_response_to_task_result() END ===")
        
        return result
    
    # Apply the hooks
    AdkDomainAgent.execute = logged_execute
    AdkDomainAgent._execute_with_adk_runner = logged_execute_with_adk
    AdkDomainAgent._run_adk_with_runner = logged_run_adk
    AdkDomainAgent._convert_messages_to_adk_content = logged_convert_messages
    AdkDomainAgent._convert_adk_response_to_task_result = logged_convert_response
    
    return {
        'execute': original_execute,
        'execute_with_adk': original_execute_with_adk,
        'run_adk': original_run_adk,
        'convert_messages': original_convert_messages,
        'convert_response': original_convert_response
    }

async def run_traced_execution():
    """Run execution with detailed AdkDomainAgent logging."""
    print("🔍 TRACING REAL ADK DOMAIN AGENT EXECUTION")
    print("="*70)
    
    # Install logging hooks
    original_methods = inject_runtime_logging()
    
    try:
        from aether_frame.bootstrap import create_ai_assistant
        from aether_frame.config.settings import Settings
        from aether_frame.contracts import TaskRequest, UniversalMessage
        
        # Create task request
        task_request = TaskRequest(
            task_id="adk_trace_execution",
            task_type="chat",
            description="Trace ADK Domain Agent execution", 
            messages=[
                UniversalMessage(
                    role="user",
                    content="What is your name and what can you do?",
                    metadata={"trace": "adk_execution"}
                )
            ],
            metadata={
                "preferred_model": "deepseek-chat",
                "framework": "adk"
            }
        )
        
        print(f"📋 Created Task Request: {task_request.task_id}")
        
        # Initialize system
        print(f"\n🚀 Initializing System...")
        settings = Settings()
        assistant = await create_ai_assistant(settings)
        
        # Execute with tracing
        print(f"\n⚡ STARTING TRACED EXECUTION...")
        print("="*70)
        
        start_time = datetime.now()
        result = await assistant.process_request(task_request)
        total_time = (datetime.now() - start_time).total_seconds()
        
        print("="*70)
        print(f"📊 EXECUTION SUMMARY")
        print(f"   Total Time: {total_time:.2f}s")
        print(f"   Final Status: {result.status}")
        print(f"   Framework: {result.metadata.get('framework')}")
        
        if result.messages:
            response = result.messages[0].content
            print(f"   Response: '{response[:150]}...'" if len(response) > 150 else f"   Response: '{response}'")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TRACED EXECUTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Restore original methods
        try:
            from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
            AdkDomainAgent.execute = original_methods['execute']
            AdkDomainAgent._execute_with_adk_runner = original_methods['execute_with_adk']
            AdkDomainAgent._run_adk_with_runner = original_methods['run_adk']
            AdkDomainAgent._convert_messages_to_adk_content = original_methods['convert_messages']
            AdkDomainAgent._convert_adk_response_to_task_result = original_methods['convert_response']
            print(f"\n🔧 Restored original methods")
        except Exception as restore_error:
            print(f"⚠️ Failed to restore methods: {restore_error}")

if __name__ == "__main__":
    success = asyncio.run(run_traced_execution())
    
    if success:
        print("\n🎉 ADK DOMAIN AGENT TRACE COMPLETED!")
        sys.exit(0)
    else:
        print("\n💥 ADK DOMAIN AGENT TRACE FAILED!")
        sys.exit(1)