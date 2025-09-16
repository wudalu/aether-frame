#!/usr/bin/env python3
"""
Debug version of single request test to trace data flow.
Shows actual data transformation at each step.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage, TaskStatus

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def pretty_print_data(title: str, data: Any, step: int):
    """Pretty print data with step number and title."""
    print(f"\n{'='*60}")
    print(f"STEP {step}: {title}")
    print(f"{'='*60}")
    
    if hasattr(data, '__dict__'):
        # For objects with __dict__, convert to dict
        data_dict = {}
        for key, value in data.__dict__.items():
            if hasattr(value, '__dict__'):
                data_dict[key] = value.__dict__
            elif isinstance(value, list):
                data_dict[key] = [v.__dict__ if hasattr(v, '__dict__') else v for v in value]
            else:
                data_dict[key] = value
        print(json.dumps(data_dict, indent=2, default=str))
    elif isinstance(data, dict):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Data type: {type(data)}")
        print(f"Data: {data}")
    print(f"{'='*60}\n")

async def trace_single_request_flow():
    """Trace the complete flow of a single request with data logging."""
    print("🔍 TRACING SINGLE REQUEST DATA FLOW")
    print("="*80)
    
    # STEP 1: Initial TaskRequest Construction
    print("\n🏗️ STEP 1: Constructing TaskRequest...")
    
    task_request = TaskRequest(
        task_id="debug_trace_test",
        task_type="chat",
        description="Debug test to trace data flow",
        messages=[
            UniversalMessage(
                role="user",
                content="Hello! Please tell me your name.",
                metadata={"debug": "initial_message"}
            )
        ],
        metadata={
            "test_type": "data_flow_trace",
            "framework": "adk",
            "preferred_model": "deepseek-chat",
            "timestamp": datetime.now().isoformat(),
            "debug_mode": True
        }
    )
    
    pretty_print_data("Initial TaskRequest", task_request, 1)
    
    # STEP 2: System Initialization
    print("🚀 STEP 2: System Initialization...")
    settings = Settings()
    assistant = await create_ai_assistant(settings)
    print("✅ AI Assistant created successfully")
    
    # STEP 3: Request Processing Entry Point
    print("\n📥 STEP 3: Entering process_request...")
    
    # Add a custom logger to intercept data flow
    class DataFlowLogger:
        def __init__(self):
            self.step_counter = 4
            
        def log_step(self, title: str, data: Any):
            pretty_print_data(title, data, self.step_counter)
            self.step_counter += 1
    
    flow_logger = DataFlowLogger()
    
    # STEP 4: Execute and trace
    print("⚙️ Starting execution with data flow tracing...")
    
    try:
        start_time = datetime.now()
        result = await assistant.process_request(task_request)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # STEP FINAL: Final Result
        flow_logger.log_step("Final TaskResult", result)
        
        # STEP ANALYSIS: Data Flow Summary
        print(f"\n📊 EXECUTION SUMMARY")
        print(f"{'='*60}")
        print(f"✅ Status: {result.status}")
        print(f"⏱️ Execution Time: {execution_time:.2f} seconds")
        print(f"📝 Response Length: {len(result.messages[-1].content) if result.messages else 0} characters")
        print(f"🏷️ Framework: {result.metadata.get('framework', 'unknown')}")
        print(f"🆔 Session ID: {result.metadata.get('session_id', 'unknown')}")
        
        # Show actual response content
        if result.messages and len(result.messages) > 0:
            print(f"\n💬 ACTUAL AI RESPONSE:")
            print(f"{'='*60}")
            print(f"Role: {result.messages[-1].role}")
            print(f"Content: {result.messages[-1].content[:200]}...")
            if result.messages[-1].metadata:
                print(f"Metadata: {result.messages[-1].metadata}")
        
        print(f"{'='*60}")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR in data flow trace: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def trace_with_custom_logging():
    """Enhanced tracing with custom logging hooks."""
    
    # Add custom logging to key components
    original_execute = None
    original_route_task = None
    
    try:
        # Hook into ExecutionEngine
        from aether_frame.execution.execution_engine import ExecutionEngine
        original_execute = ExecutionEngine.execute_task
        
        async def logged_execute_task(self, task_request):
            print(f"\n🔧 EXECUTION ENGINE: Received TaskRequest")
            print(f"Task ID: {task_request.task_id}")
            print(f"Task Type: {task_request.task_type}")
            print(f"Metadata Keys: {list(task_request.metadata.keys())}")
            
            result = await original_execute(self, task_request)
            
            print(f"\n🔧 EXECUTION ENGINE: Returning TaskResult")
            print(f"Result Status: {result.status}")
            print(f"Result Messages Count: {len(result.messages) if result.messages else 0}")
            print(f"Result Metadata: {result.metadata}")
            
            return result
        
        ExecutionEngine.execute_task = logged_execute_task
        
        # Hook into TaskRouter  
        from aether_frame.execution.task_router import TaskRouter
        original_route_task = TaskRouter.route_task
        
        async def logged_route_task(self, task_request):
            print(f"\n🛤️ TASK ROUTER: Routing request")
            print(f"Task Type: {task_request.task_type}")
            print(f"Available Tools: {len(task_request.available_tools)}")
            
            strategy = await original_route_task(self, task_request)
            
            print(f"\n🛤️ TASK ROUTER: Strategy determined")
            print(f"Framework: {strategy.framework_type}")
            print(f"Complexity: {strategy.task_complexity}")
            print(f"Execution Config Keys: {list(strategy.execution_config.keys())}")
            
            return strategy
            
        TaskRouter.route_task = logged_route_task
        
        # Run the trace
        success = await trace_single_request_flow()
        return success
        
    finally:
        # Restore original methods
        if original_execute:
            ExecutionEngine.execute_task = original_execute
        if original_route_task:
            TaskRouter.route_task = original_route_task

if __name__ == "__main__":
    success = asyncio.run(trace_with_custom_logging())
    
    if success:
        print("\n🎉 DATA FLOW TRACE COMPLETED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\n💥 DATA FLOW TRACE FAILED!")
        sys.exit(1)