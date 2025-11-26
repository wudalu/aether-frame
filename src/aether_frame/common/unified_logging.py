# -*- coding: utf-8 -*-
"""
Simplified Logging Configuration - Single Directory with Clear Flow Tracking
Unified logging approach that clearly shows execution flow in a single directory.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json


def _close_logger_handlers(logger: logging.Logger) -> None:
    """Close and detach all handlers from the provided logger."""
    handlers = list(getattr(logger, "handlers", []))
    for handler in handlers:
        try:
            handler.close()
        except Exception:
            # Swallow handler close errors during cleanup to avoid masking init
            pass
        logger.removeHandler(handler)


EXECUTION_LOGGING_ENABLED = os.getenv("AETHER_ENABLE_EXECUTION_LOGS", "1").lower() not in {
    "0",
    "false",
    "no",
}


class UnifiedLoggingConfig:
    """
    Unified logging configuration with clear execution flow tracking.
    
    Features:
    - Single 'logs' directory (no subdirectories)
    - Clear execution flow tracking
    - Structured logging with execution context
    - Key execution points logging
    """

    def __init__(self, log_base_dir: Optional[Path] = None):
        """Initialize unified logging configuration."""
        self.log_base_dir = log_base_dir or Path("logs")
        self._ensure_log_directory()

    def _ensure_log_directory(self):
        """Create single log directory."""
        self.log_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create simple .gitignore
        gitignore_path = self.log_base_dir / ".gitignore"
        if not gitignore_path.exists():
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write("# Aether Frame Unified Logs\n")
                f.write("*.log\n")
                f.write("*.json\n")

    def setup_execution_logger(
        self,
        execution_id: str,
        level: str = "INFO",
        enable_console: bool = True,
    ) -> logging.Logger:
        """
        Setup unified execution logger that tracks the complete flow.
        
        Args:
            execution_id: Unique execution identifier
            level: Log level
            enable_console: Enable console output
            
        Returns:
            logging.Logger: Configured execution logger
        """
        logger_name = f"execution.{execution_id}"
        logger = logging.getLogger(logger_name)
        _close_logger_handlers(logger)

        # Set level
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        logger.setLevel(numeric_level)
        
        # Unified formatter with execution context
        unified_formatter = ExecutionFlowFormatter()
        
        # Console handler (if enabled)
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(numeric_level)
            console_handler.setFormatter(unified_formatter)
            logger.addHandler(console_handler)
        
        # Single file handler for complete execution
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_base_dir / f"execution_{execution_id}_{timestamp}.log"
        
        file_handler = logging.FileHandler(
            filename=log_file,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Capture all details in file
        file_handler.setFormatter(unified_formatter)
        logger.addHandler(file_handler)
        
        logger.propagate = False
        return logger

    def create_execution_context(self, execution_id: str) -> 'ExecutionContext':
        """Create execution context for flow tracking."""
        logger = self.setup_execution_logger(execution_id)
        return ExecutionContext(execution_id, logger)


class ExecutionFlowFormatter(logging.Formatter):
    """Formatter that clearly shows execution flow and key data."""
    
    def format(self, record):
        """Format log record with execution flow context."""
        # Base timestamp and level
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S.%f")[:-3]  # Milliseconds
        level = record.levelname
        
        # Execution context (if available)
        execution_id = getattr(record, 'execution_id', 'unknown')
        flow_step = getattr(record, 'flow_step', '')
        component = getattr(record, 'component', record.name.split('.')[-1])
        
        # Main message
        message = record.getMessage()
        
        # Format with clear structure
        flow_prefix = f"[{flow_step}]" if flow_step else ""
        base_format = f"{timestamp} | {level:8} | {execution_id:20} | {component:15} | {flow_prefix} {message}"
        
        # Add exception info if present
        if record.exc_info:
            base_format += "\n" + self.formatException(record.exc_info)
        
        # Add key data if present
        if hasattr(record, 'key_data') and record.key_data:
            key_data_str = json.dumps(record.key_data, ensure_ascii=False, indent=2)
            base_format += f"\n>>> KEY DATA: {key_data_str}"
        
        return base_format


class ExecutionContext:
    """Execution context for tracking flow and logging key data."""
    
    def __init__(self, execution_id: str, logger: logging.Logger):
        """Initialize execution context."""
        self.execution_id = execution_id
        self.logger = logger
        self.current_step = "INIT"
        self.step_count = 0
        self.start_time = datetime.now()
        
        # Log execution start
        self.log_flow_start()
    
    def log_flow_start(self):
        """Log execution flow start."""
        self.logger.info(
            "🚀 EXECUTION STARTED",
            extra={
                'execution_id': self.execution_id,
                'flow_step': 'START',
                'component': 'SYSTEM',
                'key_data': {
                    'execution_id': self.execution_id,
                    'start_time': self.start_time.isoformat(),
                    'python_version': sys.version,
                }
            }
        )
    
    def step(self, step_name: str, component: str = "FLOW"):
        """Mark a new execution step."""
        self.step_count += 1
        self.current_step = step_name
        
        self.logger.info(
            f"➤ STEP {self.step_count}: {step_name}",
            extra={
                'execution_id': self.execution_id,
                'flow_step': f"STEP-{self.step_count:02d}",
                'component': component,
                'key_data': {
                    'step_name': step_name,
                    'step_number': self.step_count,
                    'timestamp': datetime.now().isoformat(),
                }
            }
        )
    
    def log_key_data(self, message: str, data: Dict[str, Any], component: str = "DATA"):
        """Log key execution data."""
        self.logger.info(
            f"📊 {message}",
            extra={
                'execution_id': self.execution_id,
                'flow_step': self.current_step,
                'component': component,
                'key_data': data,
            }
        )
    
    def log_success(self, message: str, data: Optional[Dict[str, Any]] = None, component: str = "SUCCESS"):
        """Log successful operation."""
        self.logger.info(
            f"✅ {message}",
            extra={
                'execution_id': self.execution_id,
                'flow_step': self.current_step,
                'component': component,
                'key_data': data or {},
            }
        )
    
    def log_warning(self, message: str, data: Optional[Dict[str, Any]] = None, component: str = "WARNING"):
        """Log warning."""
        self.logger.warning(
            f"⚠️ {message}",
            extra={
                'execution_id': self.execution_id,
                'flow_step': self.current_step,
                'component': component,
                'key_data': data or {},
            }
        )
    
    def log_error(self, message: str, error: Optional[Exception] = None, data: Optional[Dict[str, Any]] = None, component: str = "ERROR"):
        """Log error with optional exception."""
        extra_data = {
            'execution_id': self.execution_id,
            'flow_step': self.current_step,
            'component': component,
            'key_data': data or {},
        }
        
        if error:
            extra_data['key_data']['error_type'] = type(error).__name__
            extra_data['key_data']['error_details'] = str(error)
            self.logger.error(f"❌ {message}", extra=extra_data, exc_info=error)
        else:
            self.logger.error(f"❌ {message}", extra=extra_data)
    
    def log_execution_chain(self, chain_data: Dict[str, Any], component: str = "CHAIN"):
        """Log flattened execution chain data (TaskRequest->AgentRequest->ToolRequest->ToolResult->AgentResponse->TaskResult)."""
        self.logger.info(
            f"🔗 EXECUTION CHAIN",
            extra={
                'execution_id': self.execution_id,
                'flow_step': self.current_step,
                'component': component,
                'key_data': chain_data,
            }
        )
    
    def log_flow_end(self, success: bool = True, summary_data: Optional[Dict[str, Any]] = None):
        """Log execution flow end."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        status = "SUCCESS" if success else "FAILED"
        emoji = "🎉" if success else "💥"
        
        final_data = {
            'execution_id': self.execution_id,
            'total_steps': self.step_count,
            'duration_seconds': duration,
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'final_status': status,
        }
        
        if summary_data:
            final_data.update(summary_data)
        
        self.logger.info(
            f"{emoji} EXECUTION {status} - Duration: {duration:.2f}s",
            extra={
                'execution_id': self.execution_id,
                'flow_step': 'END',
                'component': 'SYSTEM',
                'key_data': final_data,
            }
        )


class NullExecutionContext:
    """No-op execution context used when per-execution logging is disabled."""

    def __init__(self, execution_id: str):
        self.execution_id = execution_id

    def log_flow_start(self):
        return

    def step(self, step_name: str, component: str = "FLOW"):
        return

    def log_key_data(self, message: str, data: Dict[str, Any], component: str = "DATA"):
        return

    def log_success(self, message: str, data: Optional[Dict[str, Any]] = None, component: str = "SUCCESS"):
        return

    def log_warning(self, message: str, data: Optional[Dict[str, Any]] = None, component: str = "WARNING"):
        return

    def log_error(self, message: str, error: Optional[Exception] = None, data: Optional[Dict[str, Any]] = None, component: str = "ERROR"):
        return

    def log_execution_chain(self, chain_data: Dict[str, Any], component: str = "CHAIN"):
        return

    def log_flow_end(self, success: bool = True, summary_data: Optional[Dict[str, Any]] = None):
        return


# Global unified logging configuration
_global_unified_config: Optional[UnifiedLoggingConfig] = None


def get_unified_logging_config() -> UnifiedLoggingConfig:
    """Get or create global unified logging configuration."""
    global _global_unified_config
    if _global_unified_config is None:
        _global_unified_config = UnifiedLoggingConfig()
    return _global_unified_config


def create_execution_context(execution_id: str) -> ExecutionContext:
    """Create execution context for flow tracking."""
    if not EXECUTION_LOGGING_ENABLED:
        return NullExecutionContext(execution_id)
    config = get_unified_logging_config()
    return config.create_execution_context(execution_id)


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Setup logger for basic needs."""
    config = get_unified_logging_config()
    
    logger = logging.getLogger(name)
    _close_logger_handlers(logger)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Simple console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(console_handler)
    
    logger.propagate = False
    return logger
