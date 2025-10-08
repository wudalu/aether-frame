# Aether Frame API Usage Guide

## Overview

This guide explains how to properly use the Aether Frame API for managing multi-agent conversations. The key principle is: **always ensure your agent exists before starting a conversation**.

## Core Concepts

### Chat Session ID (`chat_session_id`)
- **Purpose**: Business-level identifier representing a conversation thread
- **Scope**: Can span across multiple agents if needed
- **Format**: String identifier (e.g., `"user_123_conversation_456"`)
- **Usage**: Include in metadata when creating agents for session tracking

### Agent ID (`agent_id`)
- **Purpose**: Unique identifier for a specific agent instance
- **Lifecycle**: Generated when agent is created, used for all subsequent conversations
- **Format**: System-generated string (e.g., `"agent_abc123def456"`)

### Session ID (`session_id`)
- **Purpose**: Framework session identifier for conversations
- **Management**: Can be business chat_session_id or system-generated ADK session ID
- **Usage**: Used with agent_id for continuing conversations

## Recommended Usage Pattern

### Step 1: Agent Creation (Always Do This First)

**When to use**: Before starting any conversation, especially if you're unsure whether the agent exists.

**Why**: Creating an agent is idempotent-safe and ensures you have a valid agent_id for conversations.

```python
# Always create the agent first
create_request = TaskRequest(
    task_id="create_programming_agent",
    task_type="setup",
    user_context=UserContext(user_id="user_123", user_name="John Doe"),
    messages=[
        UniversalMessage(role="user", content="Setting up programming assistant")
    ],
    agent_config=AgentConfig(
        agent_type="programming_assistant",
        system_prompt="You are a helpful programming assistant",
        model_config={"model": "deepseek-chat", "temperature": 0.3}
    ),
    metadata={"chat_session_id": "conversation_456"}  # Optional: for session tracking
)

result = await ai_assistant.process_request(create_request)
agent_id = result.agent_id  # Store this for subsequent conversations
```

### Step 2: Start Conversation

**When to use**: After you have confirmed agent_id from Step 1.

```python
# Now start the actual conversation
conversation_request = TaskRequest(
    task_id="start_conversation",
    task_type="chat",
    user_context=UserContext(user_id="user_123", user_name="John Doe"),
    messages=[
        UniversalMessage(role="user", content="Can you help me with Python programming?")
    ],
    agent_id=agent_id,  # From Step 1
    session_id="conversation_456",  # Business session identifier
)

response = await ai_assistant.process_request(conversation_request)
```

### Step 3: Continue Conversation

**When to use**: For all subsequent messages in the same conversation.

```python
# Continue the conversation
continue_request = TaskRequest(
    task_id="continue_conversation",
    task_type="chat",
    user_context=UserContext(user_id="user_123", user_name="John Doe"),
    messages=[
        UniversalMessage(role="user", content="Explain list comprehensions")
    ],
    agent_id=agent_id,  # Same agent
    session_id="conversation_456",  # Same session
)

response = await ai_assistant.process_request(continue_request)
```

## Complete Example: Typical Usage Flow

```python
async def typical_conversation_flow():
    """Typical pattern: Create agent, then have conversation."""
    
    ai_assistant = await create_ai_assistant(settings)
    user_context = UserContext(user_id="user_123", user_name="Alice")
    chat_session_id = "help_session_456"
    
    # STEP 1: Always create agent first (safe even if agent type exists)
    print("Step 1: Creating agent...")
    create_agent = TaskRequest(
        task_id="create_helper_agent",
        task_type="setup",
        user_context=user_context,
        messages=[
            UniversalMessage(role="user", content="Setting up my assistant")
        ],
        agent_config=AgentConfig(
            agent_type="general_assistant",
            system_prompt="You are a helpful general assistant",
            model_config={"model": "deepseek-chat", "temperature": 0.5}
        ),
        metadata={"chat_session_id": chat_session_id}
    )
    
    agent_result = await ai_assistant.process_request(create_agent)
    agent_id = agent_result.agent_id
    print(f"✅ Agent created: {agent_id}")
    
    # STEP 2: Start meaningful conversation
    print("Step 2: Starting conversation...")
    conversation_messages = [
        "Hello, can you help me plan a vacation?",
        "I want to visit Japan in spring. What should I know?",
        "What's the best time to see cherry blossoms?",
        "Can you recommend some cities to visit?"
    ]
    
    for i, message_content in enumerate(conversation_messages):
        request = TaskRequest(
            task_id=f"conversation_turn_{i+1}",
            task_type="chat",
            user_context=user_context,
            messages=[
                UniversalMessage(role="user", content=message_content)
            ],
            agent_id=agent_id,  # Same agent throughout
            session_id=chat_session_id,  # Same session throughout
        )
        
        response = await ai_assistant.process_request(request)
        print(f"User: {message_content}")
        print(f"Assistant: {response.messages[0].content}")
        print("---")
    
    print("✅ Conversation completed successfully")
```

## Best Practices

### 1. Agent Management

**✅ Always Create First**:
```python
# Good: Always create agent before conversation
agent_result = await create_agent(agent_config)
agent_id = agent_result.agent_id

# Then use agent_id for conversations
conversation_result = await start_conversation(agent_id, session_id, messages)
```

**❌ Don't Assume Agent Exists**:
```python
# Bad: Don't assume agent_id exists
# This will fail if agent doesn't exist
conversation_result = await start_conversation("unknown_agent_id", session_id, messages)
```

### 2. Session ID Management

**✅ Use Consistent Business IDs**:
```python
# Good: Use meaningful, consistent session IDs
session_id = f"user_{user_id}_conversation_{timestamp}"
```

**❌ Don't Use Random Session IDs**:
```python
# Bad: Random IDs make debugging difficult
session_id = "abc123xyz"
```

### 3. Error Handling

**✅ Handle Agent Creation Gracefully**:
```python
try:
    agent_result = await ai_assistant.process_request(create_request)
    if agent_result.status == TaskStatus.SUCCESS:
        agent_id = agent_result.agent_id
        # Proceed with conversation
    else:
        print(f"Agent creation failed: {agent_result.error_message}")
except Exception as e:
    print(f"Error creating agent: {e}")
```

## Multiple Agents (Advanced Usage)

If you need to work with multiple agents in the same session:

```python
async def multi_agent_session():
    """Working with multiple agents in one session."""
    
    chat_session_id = "multi_agent_session_789"
    user_context = UserContext(user_id="user_123", user_name="Bob")
    
    # Create first agent
    writer_agent = await create_agent(
        agent_type="content_writer",
        system_prompt="You are a creative writer",
        chat_session_id=chat_session_id
    )
    
    # Create second agent  
    editor_agent = await create_agent(
        agent_type="content_editor", 
        system_prompt="You are a professional editor",
        chat_session_id=chat_session_id
    )
    
    # Use writer agent
    content = await chat_with_agent(
        agent_id=writer_agent.agent_id,
        session_id=chat_session_id,
        message="Write a short story about robots"
    )
    
    # Use editor agent (can access previous conversation context)
    edited_content = await chat_with_agent(
        agent_id=editor_agent.agent_id,
        session_id=chat_session_id,  # Same session enables context sharing
        message="Please edit and improve the story"
    )
```

## Summary

The fundamental rule for using Aether Frame API:

**🔑 Always create your agent first, then start conversations.**

This approach:
- ✅ Ensures agent exists before conversation
- ✅ Provides clear agent_id for subsequent calls  
- ✅ Enables proper session management
- ✅ Supports context sharing between agents when needed
- ✅ Makes debugging easier with clear error messages

Whether you're building a simple chatbot or a complex multi-agent system, following this pattern will ensure reliable and predictable behavior.