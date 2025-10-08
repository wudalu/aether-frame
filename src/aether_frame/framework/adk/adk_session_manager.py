# -*- coding: utf-8 -*-
"""ADK-specific session management."""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from ...contracts import TaskRequest
from .adk_session_models import ChatSessionInfo, CoordinationResult


class AdkSessionManager:
    """
    ADK-specific session coordinator.
    
    Manages the mapping between business-level chat sessions and ADK sessions,
    handling agent switching with create-destroy pattern for simplicity.
    """
    
    def __init__(self, session_service_factory=None):
        """Initialize ADK Session Manager."""
        self.chat_sessions: Dict[str, ChatSessionInfo] = {}  # chat_session_id -> info
        self.logger = logging.getLogger(__name__)
        
        # Session service factory for creating session services
        self.session_service_factory = session_service_factory or self._default_session_service_factory
        
        self.logger.info("ADKSessionManager initialized")
    
    def _default_session_service_factory(self):
        """Default factory that creates InMemorySessionService."""
        try:
            from google.adk.sessions import InMemorySessionService
            return InMemorySessionService()
        except ImportError:
            self.logger.warning("ADK not available, returning None for session service")
            return None
    
    def create_session_service(self):
        """Create a new session service instance."""
        return self.session_service_factory()
    
    async def coordinate_chat_session(
        self, 
        chat_session_id: str, 
        target_agent_id: str, 
        user_id: str,
        task_request: TaskRequest, 
        runner_manager
    ) -> CoordinationResult:
        """
        Coordinate chat session to ADK session mapping.
        
        Args:
            chat_session_id: Business-level session ID from frontend
            target_agent_id: Target agent for the conversation
            user_id: User identifier
            task_request: Original task request
            runner_manager: ADK RunnerManager instance
            
        Returns:
            CoordinationResult with ADK session_id and switch information
        """
        # Get or create chat session mapping
        chat_session = self.get_or_create_chat_session(chat_session_id, user_id)
        
        # Check if agent switch is needed
        current_active_agent = chat_session.active_agent_id
        
        if current_active_agent is None:
            # === First-time agent binding ===
            self.logger.info(f"First-time agent binding: binding agent {target_agent_id} for chat_session={chat_session_id}")
            chat_session.active_agent_id = target_agent_id
            return await self._create_session_for_agent(
                chat_session, target_agent_id, user_id, task_request, runner_manager
            )
        
        elif current_active_agent == target_agent_id:
            # === Same agent ===
            if chat_session.active_adk_session_id:
                # Existing session, continue conversation
                chat_session.last_activity = datetime.now()
                
                return CoordinationResult(
                    adk_session_id=chat_session.active_adk_session_id, 
                    switch_occurred=False
                )
            else:
                # Same agent but no session - create new session
                self.logger.info(f"Same agent {target_agent_id} but no session, creating new session for chat_session={chat_session_id}")
                return await self._create_session_for_agent(
                    chat_session, target_agent_id, user_id, task_request, runner_manager
                )
        
        else:
            # === Agent switch detected ===
            self.logger.info(f"Agent switch detected: {current_active_agent} -> {target_agent_id} for chat_session={chat_session_id}")
            return await self._switch_agent_session(
                chat_session, target_agent_id, user_id, task_request, runner_manager
            )

    async def _switch_agent_session(
        self,
        chat_session: ChatSessionInfo,
        target_agent_id: str,
        user_id: str,
        task_request: TaskRequest,
        runner_manager
    ) -> CoordinationResult:
        """
        Switch agent session - encapsulated switch logic for future optimization.
        
        Current implementation: Simple create-destroy pattern
        Future: Could be optimized for session reuse, caching, etc.
        """
        self.logger.info(f"Agent switch detected: {chat_session.active_agent_id} -> "
                        f"{target_agent_id} for chat_session={chat_session.chat_session_id}")
        
        previous_agent_id = chat_session.active_agent_id
        
        # 1. Extract chat history from current session before cleanup
        chat_history = None
        if chat_session.active_adk_session_id:
            self.logger.info(f"Attempting to extract chat history from session {chat_session.active_adk_session_id}")
            chat_history = await self._extract_chat_history(chat_session, runner_manager)
            self.logger.info(f"Extracted chat history: {len(chat_history) if chat_history else 0} messages")
            await self._cleanup_session_only(chat_session, runner_manager)
        
        # 2. Get runner for target agent and create session
        # Since we have agent_id, the runner should already exist
        runner_id = await runner_manager.get_runner_for_agent(target_agent_id)
        new_adk_session_id = await runner_manager._create_session_in_runner(
            runner_id, task_request=task_request, external_session_id=f"adk_session_{task_request.task_id}_{user_id}"
        )
        
        # 3. Inject chat history into new session if available
        if chat_history:
            self.logger.info(f"Attempting to inject {len(chat_history)} messages into new session {new_adk_session_id}")
            await self._inject_chat_history(runner_id, new_adk_session_id, chat_history, runner_manager)
        else:
            self.logger.info("No chat history to inject into new session")
        
        # 3. Update chat session mapping
        chat_session.active_agent_id = target_agent_id
        chat_session.active_adk_session_id = new_adk_session_id
        chat_session.active_runner_id = runner_id
        chat_session.last_switch_at = datetime.now()
        chat_session.last_activity = datetime.now()
        
        return CoordinationResult(
            adk_session_id=new_adk_session_id, 
            switch_occurred=True,
            previous_agent_id=previous_agent_id,
            new_agent_id=target_agent_id
        )
    
    async def _create_session_for_agent(
        self,
        chat_session: ChatSessionInfo,
        target_agent_id: str,
        user_id: str,
        task_request: TaskRequest,
        runner_manager
    ) -> CoordinationResult:
        """
        Create a new ADK session for the specified agent.
        
        This method handles both first-time agent binding and creating new sessions
        for existing agents.
        """
        self.logger.info(f"Creating session for agent {target_agent_id} in chat_session={chat_session.chat_session_id}")
        
        # Get runner for target agent and create session
        runner_id = await runner_manager.get_runner_for_agent(target_agent_id)
        new_adk_session_id = await runner_manager._create_session_in_runner(
            runner_id, task_request=task_request, external_session_id=f"adk_session_{task_request.task_id}_{user_id}"
        )
        
        # Update chat session mapping
        chat_session.active_agent_id = target_agent_id
        chat_session.active_adk_session_id = new_adk_session_id
        chat_session.active_runner_id = runner_id
        chat_session.last_activity = datetime.now()
        
        return CoordinationResult(
            adk_session_id=new_adk_session_id, 
            switch_occurred=False,
            new_agent_id=target_agent_id
        )
    
    def get_or_create_chat_session(self, chat_session_id: str, user_id: str) -> ChatSessionInfo:
        """Get existing or create new chat session info."""
        if chat_session_id not in self.chat_sessions:
            self.chat_sessions[chat_session_id] = ChatSessionInfo(
                user_id=user_id,
                chat_session_id=chat_session_id
            )
            self.logger.info(f"Created new chat session tracking: {chat_session_id}")
        
        return self.chat_sessions[chat_session_id]
    
    # === Session-focused management methods ===
    
    async def _cleanup_session_and_runner(self, chat_session: ChatSessionInfo, runner_manager):
        """Cleanup session and its associated runner."""
        if chat_session.active_runner_id:
            try:
                # Remove entire runner (which includes all its sessions)
                await runner_manager.cleanup_runner(chat_session.active_runner_id)
                self.logger.info(f"Cleaned up runner: {chat_session.active_runner_id}")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup runner {chat_session.active_runner_id}: {e}")
        
        # Clear session state
        self._clear_chat_session_state(chat_session)
    
    async def _cleanup_session_only(self, chat_session: ChatSessionInfo, runner_manager):
        """Cleanup only the session, preserve runner if it has other sessions."""
        if not chat_session.active_adk_session_id or not chat_session.active_runner_id:
            self._clear_chat_session_state(chat_session)
            return
            
        runner_id = chat_session.active_runner_id
        session_id = chat_session.active_adk_session_id
        
        # Remove specific session from runner
        await runner_manager.remove_session_from_runner(runner_id, session_id)
        self.logger.info(f"Removed session {session_id} from runner {runner_id}")
        
        # Check if runner has other sessions before cleanup
        session_count = await runner_manager.get_runner_session_count(runner_id)
        if session_count == 0:
            # No other sessions, safe to cleanup runner
            await runner_manager.cleanup_runner(runner_id)
            self.logger.info(f"Runner {runner_id} had no other sessions, cleaned up")
        
        # Clear session state
        self._clear_chat_session_state(chat_session)
    
    async def _create_session_in_existing_runner(
        self, 
        runner_id: str,
        target_agent_id: str, 
        user_id: str, 
        task_request: TaskRequest, 
        runner_manager
    ) -> str:
        """Create new session in existing runner."""
        # Create session in existing runner - no need for agent_config since runner already has the agent
        adk_session_id = await runner_manager._create_session_in_runner(
            runner_id, task_request=task_request, external_session_id=f"adk_session_{task_request.task_id}_{user_id}"
        )
        
        self.logger.info(f"Created new ADK session in existing runner: agent={target_agent_id}, "
                        f"runner={runner_id}, adk_session={adk_session_id}")
        return adk_session_id
    
    def _clear_chat_session_state(self, chat_session: ChatSessionInfo):
        """Clear chat session state."""
        chat_session.active_agent_id = None
        chat_session.active_adk_session_id = None
        chat_session.active_runner_id = None
    
    async def cleanup_chat_session(self, chat_session_id: str, runner_manager) -> bool:
        """Cleanup a chat session and its associated ADK resources."""
        if chat_session_id not in self.chat_sessions:
            return False
        
        chat_session = self.chat_sessions[chat_session_id]
        await self._cleanup_session_and_runner(chat_session, runner_manager)
        
        # Remove from tracking
        del self.chat_sessions[chat_session_id]
        
        self.logger.info(f"Cleaned up chat session: {chat_session_id}")
        return True

    async def _extract_chat_history(self, chat_session: ChatSessionInfo, runner_manager):
        """
        Extract chat history from current session using ADK official API.
        
        Args:
            chat_session: The chat session to extract history from
            runner_manager: Runner manager instance
            
        Returns:
            List of chat messages or None if extraction fails
        """
        try:
            runner_id = chat_session.active_runner_id
            session_id = chat_session.active_adk_session_id
            
            if not runner_id or not session_id:
                self.logger.warning(f"Cannot extract history - missing runner_id: {runner_id} or session_id: {session_id}")
                return None
            
            self.logger.info(f"🔍 DEBUG: Starting history extraction from runner {runner_id}, session {session_id}")
            
            # Get runner context
            runner_context = runner_manager.runners.get(runner_id)
            if not runner_context:
                self.logger.warning(f"Runner {runner_id} not found for history extraction")
                return None
            
            # Get SessionService instance from runner context
            session_service = runner_context.get("session_service")
            if not session_service:
                self.logger.warning(f"SessionService not found in runner {runner_id}")
                return None
            
            # Get app_name and user_id from runner context
            app_name = runner_context.get("app_name")
            user_id = runner_context.get("user_id")
            
            if not app_name or not user_id:
                self.logger.warning(f"Missing app_name({app_name}) or user_id({user_id}) in runner context")
                return None
            
            self.logger.info(f"🔍 DEBUG: Using SessionService API: app_name={app_name}, user_id={user_id}, session_id={session_id}")
            
            # Get the session object first
            try:
                session_obj = await session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id
                )
                
                if session_obj and hasattr(session_obj, 'events'):
                    self.logger.debug(f"Retrieved session with {len(session_obj.events) if session_obj.events else 0} events")
                    
                    # Log extracted events for debugging
                    for i, event in enumerate(session_obj.events):
                        author = getattr(event, 'author', 'Unknown')
                        content = getattr(event, 'content', None)
                        if content and hasattr(content, 'parts') and content.parts:
                            text = content.parts[0].text if hasattr(content.parts[0], 'text') else 'No text'
                            self.logger.debug(f"Event {i+1}: author={author}, text={text[:100]}...")
                        else:
                            self.logger.debug(f"Event {i+1}: author={author}, no content")
                    
                    # Parse events from session object
                    chat_history = await self._parse_adk_events_to_history(session_obj.events)
                    self.logger.debug(f"Parsed {len(chat_history) if chat_history else 0} messages from session events")
                    
                    # Log parsed history
                    for i, msg in enumerate(chat_history):
                        self.logger.debug(f"Parsed message {i+1}: role={msg.get('role')}, content={msg.get('content', '')[:100]}...")
                    
                    return chat_history
                else:
                    self.logger.info("No session found or session has no events attribute")
                    return []
                    
            except Exception as e:
                self.logger.error(f"Failed to get session from SessionService: {e}")
                return None
            
        except Exception as e:
            self.logger.error(f"Failed to extract chat history from session {chat_session.chat_session_id}: {e}")
            return None

    async def _parse_adk_events_to_history(self, events):
        """
        Parse ADK events to standard chat history format.
        
        Args:
            events: List of ADK Event objects
            
        Returns:
            List of chat messages in standard format
        """
        try:
            conversation_history = []
            
            for event in events:
                try:
                    # Extract author and content from Event
                    author = getattr(event, 'author', None)
                    content = getattr(event, 'content', None)
                    timestamp = getattr(event, 'timestamp', None)
                    
                    if not content:
                        continue
                    
                    # Extract text from content parts
                    content_text = ""
                    if hasattr(content, 'parts') and content.parts:
                        for part in content.parts:
                            if hasattr(part, 'text') and part.text:
                                content_text += part.text + " "
                    
                    content_text = content_text.strip()
                    if not content_text:
                        continue
                    
                    # Map author to role
                    if author == 'user':
                        role = 'user'
                    elif author and ('agent' in author.lower() or author == 'assistant'):
                        role = 'assistant'
                    else:
                        # Try to determine from content role
                        content_role = getattr(content, 'role', None)
                        if content_role == 'user':
                            role = 'user'
                        elif content_role in ['assistant', 'agent']:
                            role = 'assistant'
                        else:
                            continue  # Skip unknown roles
                    
                    conversation_history.append({
                        "role": role,
                        "content": content_text,
                        "timestamp": timestamp
                    })
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse event {type(event)}: {e}")
                    continue
            
            return conversation_history
            
        except Exception as e:
            self.logger.error(f"Failed to parse ADK events: {e}")
            return []

    async def _inject_chat_history(self, runner_id: str, session_id: str, chat_history, runner_manager):
        """
        Inject chat history into new session using ADK official API.
        
        Args:
            runner_id: Target runner ID
            session_id: Target session ID  
            chat_history: Chat history to inject (list of message objects)
            runner_manager: Runner manager instance
        """
        try:
            if not chat_history:
                self.logger.debug("No chat history to inject")
                return
            
            self.logger.info(f"Starting history injection into runner {runner_id}, session {session_id}")
            self.logger.debug(f"Injecting {len(chat_history)} messages")
            
            # Log what we're injecting for debugging
            for i, msg in enumerate(chat_history):
                self.logger.debug(f"Message {i+1} to inject: role={msg.get('role')}, content={msg.get('content', '')[:100]}...")
            
            # Get runner context
            runner_context = runner_manager.runners.get(runner_id)
            if not runner_context:
                self.logger.warning(f"Runner {runner_id} not found for history injection")
                return
            
            # Get SessionService instance
            session_service = runner_context.get("session_service")
            if not session_service:
                self.logger.warning(f"SessionService not found in runner {runner_id}")
                return
            
            # Get app_name and user_id
            app_name = runner_context.get("app_name")
            user_id = runner_context.get("user_id")
            
            if not app_name or not user_id:
                self.logger.warning(f"Missing app_name({app_name}) or user_id({user_id}) for history injection")
                return
            
            # Get the target session object
            try:
                target_session = await session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id
                )
                
                if not target_session:
                    self.logger.warning(f"Target session {session_id} not found for history injection")
                    return
                
                self.logger.debug(f"Target session found, current events: {len(target_session.events) if hasattr(target_session, 'events') and target_session.events else 0}")
                    
            except Exception as e:
                self.logger.error(f"Failed to get target session {session_id}: {e}")
                return
            
            # Create and inject events for each message using official API
            injected_count = 0
            for i, msg in enumerate(chat_history):
                try:
                    self.logger.debug(f"Creating event {i+1} from message: {msg}")
                    event = await self._create_event_from_message(msg)
                    if event:
                        self.logger.debug(f"Created event {i+1}: author={event.author}, content_parts={len(event.content.parts) if event.content and hasattr(event.content, 'parts') else 0}")
                        # Use official ADK API to append event
                        await session_service.append_event(target_session, event)
                        injected_count += 1
                        self.logger.debug(f"Successfully appended event {i+1} to session")
                    else:
                        self.logger.warning(f"Failed to create event from message {i+1}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to inject message {i+1}: {msg} - Error: {e}")
                    continue
            
            self.logger.info(f"Successfully injected {injected_count}/{len(chat_history)} events into session {session_id}")
            
            # Verify injection by getting session again
            try:
                updated_session = await session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id
                )
                if updated_session and hasattr(updated_session, 'events'):
                    self.logger.debug(f"After injection, session has {len(updated_session.events)} total events")
                
            except Exception as e:
                self.logger.warning(f"Failed to verify injection: {e}")
            
        except Exception as e:
            self.logger.error(f"Failed to inject chat history into session {session_id}: {e}")

    async def _create_event_from_message(self, message):
        """
        Create ADK Event from chat message using official ADK structures.
        
        Args:
            message: Message dict with role, content, timestamp
            
        Returns:
            ADK Event object or None if creation fails
        """
        try:
            from google.adk.events import Event
            from google.genai import types
            import uuid
            
            role = message.get('role', '')
            content_text = message.get('content', '')
            timestamp = message.get('timestamp')
            
            if not content_text:
                return None
            
            # Create ADK Content based on role
            if role == 'user':
                content = types.Content(
                    role='user',
                    parts=[types.Part(text=content_text)]
                )
                author = 'user'
            elif role in ['assistant', 'agent']:
                content = types.Content(
                    role='assistant',
                    parts=[types.Part(text=content_text)]
                )
                author = 'agent'  # Use generic agent name
            else:
                self.logger.warning(f"Unknown role: {role}")
                return None
            
            # Create Event with proper structure
            event = Event(
                invocation_id=str(uuid.uuid4()),
                author=author,
                content=content,
                timestamp=timestamp if timestamp else datetime.now(timezone.utc)
            )
            
            return event
            
        except ImportError as e:
            self.logger.error(f"ADK Event/types classes not available: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create event from message: {e}")
            return None