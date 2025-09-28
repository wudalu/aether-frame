# Aether Frame - Core Execution Flow and Data Transformation

## Overview

This document focuses on the core execution flow and key data transformations in Aether Frame. It provides essential flow diagrams and data mapping without implementation details.

**Last Updated**: September 2024  
**Implementation Status**: ADK-First Implementation Complete

---

## Table of Contents

1. [System Bootstrap Flow](#system-bootstrap-flow)
2. [Core Request Processing Flow](#core-request-processing-flow)
3. [Three Execution Modes](#three-execution-modes)
4. [Data Transformation Pipeline](#data-transformation-pipeline)
5. [Session Management Flow](#session-management-flow)
6. [Error Handling Flow](#error-handling-flow)

---

## System Bootstrap Flow

### 5-Phase Initialization

```mermaid
sequenceDiagram
    participant USER as Application
    participant BOOT as Bootstrap System
    participant REG as Framework Registry
    participant TOOL as Tool Service
    participant ADK as ADK Adapter
    participant AM as Agent Manager
    participant EE as Execution Engine
    participant AI as AI Assistant

    USER->>BOOT: create_ai_assistant(settings)
    
    Note over BOOT: Phase 1: Framework Registry
    BOOT->>REG: Initialize registry
    
    Note over BOOT: Phase 2: Tool Service
    BOOT->>TOOL: Initialize with builtin tools
    
    Note over BOOT: Phase 3: ADK Framework Adapter
    BOOT->>REG: Auto-load ADK adapter
    REG->>ADK: Initialize with dependencies
    
    Note over BOOT: Phase 4: Agent Manager
    BOOT->>AM: Initialize for agent lifecycle
    
    Note over BOOT: Phase 5: Execution Engine
    BOOT->>EE: Initialize with task router
    
    BOOT->>AI: Create AI Assistant
    AI-->>USER: System ready
```

---

## Core Request Processing Flow

### High-Level Flow

```mermaid
flowchart TD
    START([TaskRequest]) --> VALIDATE{Request Valid?}
    VALIDATE -->|Valid| ROUTE[Task Router]
    VALIDATE -->|Invalid| ERROR[Validation Error]
    
    ROUTE --> STRATEGY[ExecutionStrategy: ADK]
    STRATEGY --> REGISTRY[Framework Registry]
    REGISTRY --> ADAPTER[ADK Framework Adapter]
    
    ADAPTER --> MODE{Execution Mode?}
    MODE -->|agent_id + session_id| CASE1[Continue Session]
    MODE -->|agent_id only| CASE2[New Session]  
    MODE -->|agent_config only| CASE3[Create Agent]
    
    CASE1 --> EXECUTE[Execute via Domain Agent]
    CASE2 --> EXECUTE
    CASE3 --> EXECUTE
    
    EXECUTE --> RESULT[TaskResult]
    ERROR --> RESULT
    RESULT --> END([Return to User])
```

### Component Flow

```mermaid
sequenceDiagram
    participant USER as User
    participant AI as AI Assistant
    participant EE as Execution Engine
    participant TR as Task Router
    participant REG as Framework Registry
    participant ADK as ADK Adapter
    
    USER->>AI: TaskRequest
    AI->>AI: Validate request
    AI->>EE: execute_task()
    EE->>TR: route_task()
    TR-->>EE: ExecutionStrategy (ADK)
    EE->>REG: get_adapter(ADK)
    REG-->>EE: AdkFrameworkAdapter
    EE->>ADK: execute_task()
    ADK-->>EE: TaskResult
    EE-->>AI: TaskResult
    AI-->>USER: Response
```

---

## Three Execution Modes

### Mode Overview

```mermaid
flowchart TD
    REQUEST[TaskRequest] --> CHECK{Contains?}
    
    CHECK -->|agent_config| MODE3[Mode 3: Create New]
    CHECK -->|agent_id + session_id| MODE1[Mode 1: Continue]
    CHECK -->|agent_id only| MODE2[Mode 2: New Session]
    
    MODE3 --> CREATE[Create Agent & Session]
    MODE1 --> CONTINUE[Use Existing Session]
    MODE2 --> NEWSESSION[Create New Session]
    
    CREATE --> EXECUTE[Execute Task]
    CONTINUE --> EXECUTE
    NEWSESSION --> EXECUTE
    
    EXECUTE --> RESULT[TaskResult with IDs]
```

### Mode 1: Continue Existing Session

```mermaid
sequenceDiagram
    participant ADK as ADK Adapter
    participant AM as Agent Manager
    participant RM as Runner Manager
    participant DA as Domain Agent
    
    Note over ADK: Input: agent_id + session_id
    
    ADK->>AM: get_agent(agent_id)
    AM-->>ADK: domain_agent
    ADK->>ADK: Get runner_id from mapping
    ADK->>RM: Get runner_context(runner_id)
    RM-->>ADK: runner_context with session
    ADK->>DA: execute() with existing session
    DA-->>ADK: TaskResult
    ADK->>ADK: Add agent_id + session_id to result
```

### Mode 2: New Session for Existing Agent

```mermaid
sequenceDiagram
    participant ADK as ADK Adapter
    participant AM as Agent Manager
    participant RM as Runner Manager
    participant DA as Domain Agent
    
    Note over ADK: Input: agent_id only
    
    ADK->>AM: get_agent(agent_id)
    AM-->>ADK: domain_agent
    ADK->>ADK: Generate new session_id
    ADK->>RM: create_session_in_runner()
    RM-->>ADK: new_session_id
    ADK->>ADK: Update session mappings
    ADK->>DA: execute() with new session
    DA-->>ADK: TaskResult
    ADK->>ADK: Add agent_id + new_session_id to result
```

### Mode 3: Create New Agent and Session

```mermaid
sequenceDiagram
    participant ADK as ADK Adapter
    participant AM as Agent Manager
    participant RM as Runner Manager
    participant DA as Domain Agent Factory
    
    Note over ADK: Input: agent_config only
    
    ADK->>ADK: Generate agent_id + session_id
    ADK->>DA: create_domain_agent()
    DA-->>ADK: domain_agent with adk_agent
    ADK->>AM: Register agent directly
    ADK->>RM: create_runner_and_session()
    RM-->>ADK: runner_id + session_id
    ADK->>ADK: Store all mappings
    ADK->>DA: execute() with new context
    DA-->>ADK: TaskResult
    ADK->>ADK: Add agent_id + session_id to result
```

---

## Data Transformation Pipeline

### Complete Data Flow Chain

```mermaid
flowchart TD
    subgraph "Request Chain"
        TR[TaskRequest] --> AR[AgentRequest] 
        AR --> TOOL[ToolRequest]
        TOOL --> TRESP[ToolResult]
        TRESP --> ARESP[Agent Processing]
        ARESP --> RESULT[TaskResult]
    end
    
    subgraph "Context Chain"
        RC[RuntimeContext] --> EC[ExecutionContext]
        EC --> SC[SessionContext]
        SC --> UC[UserContext]
    end
    
    RC -.-> AR
    EC -.-> TOOL
    SC -.-> ARESP
```

### Data Transformation Interfaces

#### 1. TaskRequest → AgentRequest
**Interface**: `AdkFrameworkAdapter.execute_task() → AdkDomainAgent.execute()`
- **Input**: TaskRequest with agent_id/session_id/agent_config
- **Context**: RuntimeContext built from agent, runner, session state
- **Output**: AgentRequest with unified runtime_options

#### 2. AgentRequest → ToolRequest (Internal ADK Flow)
**Interface**: `AdkDomainAgent._get_adk_tools() → chat_log_function()`
- **Input**: ADK tool invocation during agent execution
- **Transform**: ADK parameters → ToolRequest structure 
- **Context**: session_id, tool_service from runtime_context

#### 3. ToolRequest → ToolResult
**Interface**: `ChatLogTool.execute(tool_request) → ToolResult`
- **Input**: ToolRequest with tool_name, parameters, session_id
- **Processing**: Tool-specific execution logic
- **Output**: ToolResult with status, result_data, execution_time

#### 4. ToolResult → Agent Processing → TaskResult
**Interface**: `AdkDomainAgent._execute_with_adk_runner() → TaskResult`
- **Input**: Tool results integrated into ADK response
- **Transform**: ADK response → UniversalMessage format
- **Output**: TaskResult with agent_id/session_id for continuation

### Context Construction and Passing

#### RuntimeContext Building
**Interface**: `AdkFrameworkAdapter._build_runtime_context()`
- **Sources**: AgentManager, RunnerManager, session mappings
- **Fields**: session_id, user_id, agent_id, framework_session, runner_context
- **Usage**: Passed to domain agent for execution context

#### Context Propagation Flow
1. **TaskRequest Context**: agent_id, session_id preserved throughout chain
2. **RuntimeContext Assembly**: Framework adapter builds from multiple sources
3. **AgentRequest Context**: RuntimeContext passed as runtime_options
4. **Tool Execution Context**: session_id extracted for tool requests
5. **TaskResult Context**: agent_id/session_id added for continuation

---

## Session Management Flow

### Session Lifecycle States

```mermaid
stateDiagram-v2
    [*] --> Requested
    
    Requested --> Creating: agent_config
    Requested --> Continuing: agent_id + session_id
    Requested --> NewSession: agent_id only
    
    Creating --> AgentCreation
    AgentCreation --> RunnerCreation
    RunnerCreation --> SessionCreation
    SessionCreation --> Active
    
    Continuing --> Validation
    Validation --> Active: found
    Validation --> Error: not found
    
    NewSession --> SessionCreation
    SessionCreation --> Active
    
    Active --> Processing
    Processing --> Active: continue
    Processing --> [*]: complete
    
    Error --> [*]
```

### Storage Structure

```mermaid
erDiagram
    AgentManager ||--o{ Agent : manages
    Agent {
        string agent_id
        string agent_type
        datetime created_at
        datetime last_activity
    }
    
    AdkFrameworkAdapter ||--o{ AgentRunnerMapping : tracks
    AgentRunnerMapping {
        string agent_id
        string runner_id
        list session_ids
    }
    
    RunnerManager ||--o{ Runner : manages
    Runner {
        string runner_id
        object runner_instance
        object session_service
        dict sessions
        datetime created_at
    }
    
    Runner ||--o{ Session : contains
    Session {
        string session_id
        object adk_session
        string user_id
    }
```

---


## Summary

**Core Execution Pattern:**
1. **Bootstrap**: 5-phase system initialization
2. **Request**: Validation → Routing → Framework Selection
3. **Execution**: Three modes based on input (continue/new session/create agent)
4. **Response**: Enhanced with agent_id + session_id for follow-up

**Key Data Transformations:**
- TaskRequest → ExecutionStrategy (complexity analysis)
- TaskRequest → AgentRequest (runtime context assembly)
- ADK Response → TaskResult (session metadata addition)

**Session Management:**
- Persistent agent storage via AgentManager
- ADK session lifecycle via RunnerManager  
- Multi-session support per agent
- Clean error handling with context preservation

This document will be updated when core execution flows or data transformation processes change.