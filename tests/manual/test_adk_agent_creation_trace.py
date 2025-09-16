#!/usr/bin/env python3
"""
Trace ADK Agent creation and configuration to understand what business logic ADK executes.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

def trace_adk_agent_creation():
    """Trace the creation and configuration of ADK Agent."""
    
    from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
    
    # Hook _create_adk_agent method
    original_create_adk_agent = AdkDomainAgent._create_adk_agent
    
    async def traced_create_adk_agent(self):
        print(f"\n🤖 === _create_adk_agent() START ===")
        print(f"   Agent ID: {self.agent_id}")
        print(f"   Config Keys: {list(self.config.keys())}")
        
        # Show detailed config
        for key, value in self.config.items():
            if isinstance(value, dict):
                print(f"   Config[{key}]: {list(value.keys())} (dict)")
            else:
                print(f"   Config[{key}]: {str(value)[:100]}..." if len(str(value)) > 100 else f"   Config[{key}]: {value}")
        
        try:
            print(f"   🔍 Importing ADK Agent...")
            from google.adk import Agent
            print(f"   ✅ ADK Agent class imported successfully")
            
            # Get model configuration 
            print(f"   🔧 Getting model configuration...")
            model_identifier = self._get_model_configuration()
            print(f"   📋 Model Identifier: {model_identifier}")
            
            # Create model via factory
            print(f"   🏭 Creating model via AdkModelFactory...")
            from aether_frame.framework.adk.model_factory import AdkModelFactory
            model = AdkModelFactory.create_model(model_identifier, self._get_settings())
            print(f"   ✅ Model created: {type(model).__name__}")
            
            # Extract agent configuration
            agent_name = self.config.get("name", self.agent_id)
            agent_description = self.config.get("description", "ADK Domain Agent")
            agent_instruction = self.config.get("system_prompt", "You are a helpful AI assistant.")
            
            print(f"   📝 ADK Agent Configuration:")
            print(f"      Name: {agent_name}")
            print(f"      Description: {agent_description}")
            print(f"      Instruction: {agent_instruction[:200]}..." if len(agent_instruction) > 200 else f"      Instruction: {agent_instruction}")
            print(f"      Model: {model}")
            
            # Create the actual ADK Agent
            print(f"   🚀 Creating ADK Agent instance...")
            self.adk_agent = Agent(
                name=agent_name,
                description=agent_description,
                instruction=agent_instruction,
                model=model,
            )
            print(f"   ✅ ADK Agent created successfully: {type(self.adk_agent).__name__}")
            print(f"   🔍 ADK Agent Details:")
            print(f"      Agent Name: {self.adk_agent.name}")
            print(f"      Agent Description: {self.adk_agent.description}")
            print(f"      Agent Instruction: {self.adk_agent.instruction[:200]}..." if len(self.adk_agent.instruction) > 200 else f"      Agent Instruction: {self.adk_agent.instruction}")
            
        except ImportError as e:
            print(f"   ⚠️ ImportError - ADK not available: {e}")
            self.adk_agent = None
        except Exception as e:
            print(f"   ❌ Exception during ADK agent creation: {e}")
            import traceback
            traceback.print_exc()
            self.adk_agent = None
        
        print(f"🤖 === _create_adk_agent() END ===")
        print(f"   Final ADK Agent: {self.adk_agent is not None}")
    
    AdkDomainAgent._create_adk_agent = traced_create_adk_agent
    return original_create_adk_agent

def trace_agent_config_building():
    """Trace how agent config is built from task request."""
    
    from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
    
    # Hook _build_agent_config_from_task method
    original_build_config = AdkFrameworkAdapter._build_agent_config_from_task
    
    def traced_build_config(self, task_request, strategy):
        print(f"\n🏗️ === _build_agent_config_from_task() START ===")
        print(f"   Task ID: {task_request.task_id}")
        print(f"   Task Type: {task_request.task_type}")
        print(f"   Task Description: {task_request.description}")
        print(f"   Task Metadata: {task_request.metadata}")
        
        # Call original method
        config = original_build_config(self, task_request, strategy)
        
        print(f"   🔧 Built AgentConfig:")
        print(f"      Framework Type: {config.framework_type}")
        print(f"      Agent Type: {config.agent_type}")
        print(f"      Name: {config.name}")
        print(f"      Description: {config.description}")
        print(f"      Model Config: {config.model_config}")
        print(f"      System Prompt: {config.system_prompt[:200]}..." if len(config.system_prompt) > 200 else f"      System Prompt: {config.system_prompt}")
        print(f"      Capabilities: {config.capabilities}")
        print(f"      Tool Permissions: {config.tool_permissions}")
        print(f"      Max Iterations: {config.max_iterations}")
        print(f"      Timeout: {config.timeout}")
        
        print(f"🏗️ === _build_agent_config_from_task() END ===")
        return config
    
    AdkFrameworkAdapter._build_agent_config_from_task = traced_build_config
    return original_build_config

async def run_adk_agent_creation_trace():
    """Run execution with ADK agent creation tracing."""
    print("🔍 TRACING ADK AGENT CREATION AND CONFIGURATION")
    print("="*80)
    
    # Install tracing hooks
    original_create = trace_adk_agent_creation()
    original_build = trace_agent_config_building()
    
    try:
        from aether_frame.bootstrap import create_ai_assistant
        from aether_frame.config.settings import Settings
        from aether_frame.contracts import TaskRequest, UniversalMessage
        
        # Create a task request that will trigger agent creation
        task_request = TaskRequest(
            task_id="adk_agent_creation_trace",
            task_type="chat",
            description="Trace ADK agent creation and configuration",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Hello, I want to understand how you work internally.",
                    metadata={"trace": "agent_creation"}
                )
            ],
            metadata={
                "preferred_model": "deepseek-chat",
                "framework": "adk",
                "temperature": 0.7,
                "max_tokens": 1000,
                "required_capabilities": ["conversational"],
                "custom_instruction": "You are an expert AI assistant that explains technical concepts clearly."
            }
        )
        
        print(f"📋 Task Request Created: {task_request.task_id}")
        
        # Initialize system (this will trigger agent creation)
        print(f"\n🚀 Initializing System (will create ADK agents)...")
        settings = Settings()
        assistant = await create_ai_assistant(settings)
        
        # Execute request (this will create session agents)
        print(f"\n⚡ Executing Request (will create session-specific agents)...")
        
        # Set shorter timeout to avoid hanging
        try:
            result = await asyncio.wait_for(
                assistant.process_request(task_request), 
                timeout=20.0  # 20 second timeout
            )
            
            print(f"\n📊 EXECUTION COMPLETED")
            print(f"   Status: {result.status}")
            print(f"   Framework: {result.metadata.get('framework')}")
            
            if result.messages:
                response = result.messages[0].content
                print(f"   Response: '{response[:150]}...'" if len(response) > 150 else f"   Response: '{response}'")
                
        except asyncio.TimeoutError:
            print(f"\n⏰ Execution timed out (but agent creation was traced)")
            
    except Exception as e:
        print(f"\n❌ TRACE FAILED: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Restore original methods
        try:
            from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
            from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
            AdkDomainAgent._create_adk_agent = original_create
            AdkFrameworkAdapter._build_agent_config_from_task = original_build
            print(f"\n🔧 Restored original methods")
        except Exception as restore_error:
            print(f"⚠️ Failed to restore methods: {restore_error}")

if __name__ == "__main__":
    asyncio.run(run_adk_agent_creation_trace())
    print("\n🎉 ADK AGENT CREATION TRACE COMPLETED!")