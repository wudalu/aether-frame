# -*- coding: utf-8 -*-
"""Unified Interaction Logger - Everything in One Clear Log File."""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class UnifiedInteractionLogger:
    """
    Unified logger that records everything in one clear, readable log file.
    
    Records:
    - User requests
    - System processing steps  
    - LLM requests & responses
    - Session management
    - Errors and performance
    
    All in chronological order in a single file for easy reading.
    """
    
    def __init__(self, log_file_path: Optional[str] = None):
        """Initialize unified interaction logger."""
        
        # Single log file
        if log_file_path:
            self.log_file = Path(log_file_path)
        else:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            self.log_file = log_dir / f"interactions_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Setup logger
        self.logger = logging.getLogger("unified_interactions")
        self.logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler with clear formatting
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        
        # Simple, readable format
        formatter = logging.Formatter(
            '%(asctime)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Also log to console for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def log_user_request(self, session_id: str, task_id: str, user_message: str, agent_config: Dict[str, Any] = None):
        """Log user request."""
        session_info = f"[Session: {session_id}]" if session_id else "[New Session]"
        agent_info = f"Agent: {agent_config.get('agent_type', 'default')}" if agent_config else ""
        
        self.logger.info(f"👤 USER REQUEST {session_info}")
        self.logger.info(f"   └─ Task: {task_id}")
        self.logger.info(f"   └─ Message: {user_message}")
        if agent_info:
            self.logger.info(f"   └─ {agent_info}")
    
    def log_session_action(self, action: str, session_id: str, details: Dict[str, Any] = None):
        """Log session management actions."""
        action_emoji = {
            "created": "🆕",
            "found": "🔍", 
            "continued": "🔄",
            "error": "❌"
        }.get(action, "ℹ️")
        
        self.logger.info(f"{action_emoji} SESSION {action.upper()}: {session_id}")
        if details:
            for key, value in details.items():
                self.logger.info(f"   └─ {key}: {value}")
    
    def log_llm_request(self, model: str, provider: str, messages: list, parameters: Dict[str, Any]):
        """Log LLM request."""
        # Extract the user message for clarity
        user_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")[:100] + ("..." if len(msg.get("content", "")) > 100 else "")
                break
        
        self.logger.info(f"🤖 LLM REQUEST → {provider}/{model}")
        self.logger.info(f"   └─ User: {user_msg}")
        self.logger.info(f"   └─ Params: temp={parameters.get('temperature', 'N/A')}, max_tokens={parameters.get('max_tokens', 'N/A')}")
    
    def log_llm_response(self, response_content: str, execution_time_ms: float, token_usage: Dict[str, Any] = None, error: str = None):
        """Log LLM response."""
        if error:
            self.logger.info(f"❌ LLM RESPONSE ERROR ({execution_time_ms:.1f}ms)")
            self.logger.info(f"   └─ Error: {error}")
        else:
            # Show first part of response for context
            preview = response_content[:150] + ("..." if len(response_content) > 150 else "")
            
            self.logger.info(f"✅ LLM RESPONSE ({execution_time_ms:.1f}ms)")
            self.logger.info(f"   └─ Content: {preview}")
            self.logger.info(f"   └─ Length: {len(response_content)} characters")
            
            if token_usage:
                total_tokens = token_usage.get('total_tokens', 'N/A')
                self.logger.info(f"   └─ Tokens: {total_tokens}")
    
    def log_system_action(self, action: str, details: Dict[str, Any] = None):
        """Log system actions."""
        self.logger.info(f"⚙️  SYSTEM: {action}")
        if details:
            for key, value in details.items():
                self.logger.info(f"   └─ {key}: {value}")
    
    def log_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """Log errors."""
        self.logger.info(f"💥 ERROR: {error_type}")
        self.logger.info(f"   └─ Message: {error_message}")
        if context:
            for key, value in context.items():
                self.logger.info(f"   └─ {key}: {value}")
    
    def log_performance(self, operation: str, duration_ms: float, details: Dict[str, Any] = None):
        """Log performance metrics."""
        self.logger.info(f"⏱️  PERFORMANCE: {operation} ({duration_ms:.1f}ms)")
        if details:
            for key, value in details.items():
                self.logger.info(f"   └─ {key}: {value}")
    
    def log_separator(self, label: str = None):
        """Log a visual separator for readability."""
        if label:
            self.logger.info(f"{'='*20} {label} {'='*20}")
        else:
            self.logger.info("="*50)
    
    def log_interaction_complete(self, session_id: str, task_id: str, success: bool, summary: Dict[str, Any] = None):
        """Log interaction completion."""
        status = "✅ COMPLETED" if success else "❌ FAILED"
        self.logger.info(f"🏁 INTERACTION {status}")
        self.logger.info(f"   └─ Session: {session_id}")
        self.logger.info(f"   └─ Task: {task_id}")
        
        if summary:
            for key, value in summary.items():
                self.logger.info(f"   └─ {key}: {value}")


# Global unified logger instance
_global_unified_logger = None


def get_unified_logger() -> UnifiedInteractionLogger:
    """Get the global unified logger instance."""
    global _global_unified_logger
    if _global_unified_logger is None:
        _global_unified_logger = UnifiedInteractionLogger()
    return _global_unified_logger


# Context manager for complete interaction logging
class InteractionSession:
    """Context manager for logging a complete interaction session."""
    
    def __init__(self, session_id: str, task_id: str, user_message: str, agent_config: Dict[str, Any] = None):
        self.session_id = session_id
        self.task_id = task_id
        self.user_message = user_message
        self.agent_config = agent_config
        self.start_time = None
        self.logger = get_unified_logger()
        
    def __enter__(self):
        self.start_time = datetime.now()
        
        # Start logging the interaction
        self.logger.log_separator(f"NEW INTERACTION {self.task_id}")
        self.logger.log_user_request(self.session_id, self.task_id, self.user_message, self.agent_config)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds() * 1000
        
        if exc_type:
            self.logger.log_error(
                exc_type.__name__, 
                str(exc_val),
                {"task_id": self.task_id, "session_id": self.session_id}
            )
            success = False
        else:
            success = True
        
        self.logger.log_interaction_complete(
            self.session_id, 
            self.task_id, 
            success,
            {"total_duration_ms": f"{duration:.1f}"}
        )
        self.logger.log_separator()
    
    def log_session_created(self, session_id: str, agent_type: str):
        """Log session creation."""
        self.logger.log_session_action("created", session_id, {"agent_type": agent_type})
    
    def log_session_found(self, session_id: str):
        """Log session found."""
        self.logger.log_session_action("found", session_id)
    
    def log_llm_call(self, model: str, provider: str, messages: list, parameters: Dict[str, Any]):
        """Log LLM request."""
        self.logger.log_llm_request(model, provider, messages, parameters)
    
    def log_llm_result(self, response_content: str, execution_time_ms: float, token_usage: Dict[str, Any] = None, error: str = None):
        """Log LLM response.""" 
        self.logger.log_llm_response(response_content, execution_time_ms, token_usage, error)
    
    def log_step(self, step_name: str, details: Dict[str, Any] = None):
        """Log a processing step."""
        self.logger.log_system_action(step_name, details)


def log(message: str, level: str = "info"):
    """Logging function for quick messages."""
    logger = get_unified_logger()
    if level == "error":
        logger.log_error("GENERAL", message)
    else:
        logger.log_system_action(message)