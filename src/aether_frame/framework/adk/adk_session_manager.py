# -*- coding: utf-8 -*-
"""ADK-specific session management."""

import logging
from datetime import datetime
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
        
        if current_active_agent != target_agent_id:
            # === Agent switch detected ===
            return await self._switch_agent_session(
                chat_session, target_agent_id, user_id, task_request, runner_manager
            )
        
        else:
            # === Same agent, continue conversation ===
            if chat_session.active_adk_session_id:
                # Existing session, update activity
                chat_session.last_activity = datetime.now()
                
                return CoordinationResult(
                    adk_session_id=chat_session.active_adk_session_id, 
                    switch_occurred=False
                )
            else:
                # No session exists but agent is same, create session in existing runner
                # Since we're continuing with the same agent, the runner should already exist
                if chat_session.active_runner_id:
                    # Use existing runner
                    runner_id = chat_session.active_runner_id
                    new_adk_session_id = await self._create_session_in_existing_runner(
                        runner_id, target_agent_id, user_id, task_request, runner_manager
                    )
                else:
                    # TODO: Investigate why we don't have active_runner_id for the same agent
                    # This should not happen in normal flow - indicates a bug in session state management
                    raise RuntimeError(
                        f"Chat session {chat_session.chat_session_id} has active_agent_id "
                        f"{chat_session.active_agent_id} but no active_runner_id. "
                        f"This indicates a session state inconsistency."
                    )
                
                chat_session.active_adk_session_id = new_adk_session_id
                chat_session.active_runner_id = runner_id
                chat_session.last_activity = datetime.now()
                
                return CoordinationResult(
                    adk_session_id=new_adk_session_id, 
                    switch_occurred=False
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
            chat_history = await self._extract_chat_history(chat_session, runner_manager)
            await self._cleanup_session_only(chat_session, runner_manager)
        
        # 2. Get runner for target agent and create session
        # Since we have agent_id, the runner should already exist
        runner_id = await runner_manager.get_runner_for_agent(target_agent_id)
        new_adk_session_id = await runner_manager._create_session_in_runner(
            runner_id, external_session_id=f"adk_session_{task_request.task_id}_{user_id}"
        )
        
        # 3. Inject chat history into new session if available
        if chat_history:
            await self._inject_chat_history(runner_id, new_adk_session_id, chat_history, runner_manager)
        
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
            runner_id, external_session_id=f"adk_session_{task_request.task_id}_{user_id}"
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
        Extract chat history from current session before cleanup.
        
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
            
            # Get runner context
            runner_context = runner_manager.runners.get(runner_id)
            if not runner_context:
                self.logger.warning(f"Runner {runner_id} not found for history extraction")
                return None
            
            # Get ADK session
            adk_session = runner_context["sessions"].get(session_id)
            if not adk_session:
                self.logger.warning(f"ADK session {session_id} not found for history extraction")
                return None
            
            # Extract chat history from ADK session
            # TODO: Implement actual ADK session history extraction
            # This depends on ADK's session API for retrieving conversation history
            chat_history = await self._get_adk_session_history(adk_session)
            
            self.logger.info(f"Extracted {len(chat_history) if chat_history else 0} messages from session {session_id}")
            return chat_history
            
        except Exception as e:
            self.logger.error(f"Failed to extract chat history from session {chat_session.chat_session_id}: {e}")
            return None

    async def _inject_chat_history(self, runner_id: str, session_id: str, chat_history, runner_manager):
        """
        Inject chat history into new session.
        
        Args:
            runner_id: Target runner ID
            session_id: Target session ID  
            chat_history: Chat history to inject
            runner_manager: Runner manager instance
        """
        try:
            if not chat_history:
                return
            
            # Get runner context
            runner_context = runner_manager.runners.get(runner_id)
            if not runner_context:
                self.logger.warning(f"Runner {runner_id} not found for history injection")
                return
            
            # Get ADK session
            adk_session = runner_context["sessions"].get(session_id)
            if not adk_session:
                self.logger.warning(f"ADK session {session_id} not found for history injection")
                return
            
            # Inject chat history into ADK session
            # TODO: Implement actual ADK session history injection
            # This depends on ADK's session API for setting conversation history
            await self._set_adk_session_history(adk_session, chat_history)
            
            self.logger.info(f"Injected {len(chat_history)} messages into session {session_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to inject chat history into session {session_id}: {e}")

    async def _get_adk_session_history(self, adk_session):
        """
        Get chat history from ADK session.
        
        Args:
            adk_session: ADK session instance
            
        Returns:
            List of chat messages in ADK format
        """
        try:
            # ADK sessions store conversation history in session.state
            # Based on Google ADK documentation, conversation history is typically stored as:
            # session.state['conversation_history'] or session.state['messages']
            
            if hasattr(adk_session, 'state'):
                # Try common conversation history keys
                history_keys = ['conversation_history', 'messages', 'chat_history', 'history']
                
                for key in history_keys:
                    if key in adk_session.state:
                        history = adk_session.state[key]
                        if isinstance(history, list):
                            self.logger.info(f"Found conversation history in session.state['{key}'] with {len(history)} messages")
                            return history
                
                # If no specific history key found, check if there are any message-like structures
                for key, value in adk_session.state.items():
                    if isinstance(value, list) and len(value) > 0:
                        # Check if this looks like message history (has role/content structure)
                        first_item = value[0]
                        if isinstance(first_item, dict) and ('role' in first_item or 'author' in first_item):
                            self.logger.info(f"Found message-like history in session.state['{key}'] with {len(value)} messages")
                            return value
                
                self.logger.info("No conversation history found in session state")
                return []
            else:
                self.logger.warning("ADK session does not have 'state' attribute")
                return []
                
        except Exception as e:
            self.logger.error(f"Failed to get ADK session history: {e}")
            return []

    async def _set_adk_session_history(self, adk_session, chat_history):
        """
        Set chat history in ADK session.
        
        Args:
            adk_session: ADK session instance
            chat_history: Chat history to set (list of message objects)
        """
        try:
            if not chat_history:
                return
                
            if hasattr(adk_session, 'state'):
                # Store conversation history in session state
                # Use 'conversation_history' as the primary key for consistency
                adk_session.state['conversation_history'] = chat_history
                
                # Also store in 'messages' for compatibility with different ADK patterns
                adk_session.state['messages'] = chat_history
                
                self.logger.info(f"Set conversation history with {len(chat_history)} messages in session state")
            else:
                self.logger.warning("ADK session does not have 'state' attribute for history injection")
                
        except Exception as e:
            self.logger.error(f"Failed to set ADK session history: {e}")