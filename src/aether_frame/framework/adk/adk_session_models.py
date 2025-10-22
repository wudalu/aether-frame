# -*- coding: utf-8 -*-
"""ADK-specific session management models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Set

from ...contracts import KnowledgeSource, TaskRequest


@dataclass
class ChatSessionInfo:
    """ADK chat session tracking information."""
    
    user_id: str
    chat_session_id: str
    
    # Single active session state
    active_agent_id: Optional[str] = None
    active_adk_session_id: Optional[str] = None  
    active_runner_id: Optional[str] = None
    available_knowledge: List[KnowledgeSource] = field(default_factory=list)
    synced_knowledge_sources: Set[str] = field(default_factory=set)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    last_switch_at: Optional[datetime] = None


@dataclass
class CoordinationResult:
    """Result of ADK session coordination."""
    
    adk_session_id: str
    switch_occurred: bool
    previous_agent_id: Optional[str] = None
    new_agent_id: Optional[str] = None
