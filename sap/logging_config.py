"""Structured logging system with JSON output and UI integration.

Provides:
    - JSON formatter for machine-readable log entries
    - Rotating file handler (max 10 MB, 5 backups)
    - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
    - Thread-local context enrichment (transaction, field, session_id, etc.)
    - Browser log viewer UI integration (NiceGUI)
    - Convenience logging functions

Architecture:
    The logging system bridges Python's standard logging with structured output
    for both file storage and browser debugging. Each log entry includes:
    - Timestamp (ISO format)
    - Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Logger name and module/function/line info
    - Message and exception details (if applicable)
    - Thread-local context (transaction, field_name, session_id, etc.)
    - Custom context fields via the 'extra' dict parameter

Example:
    ```python
    from sap.logging_config import get_logger, setup_logging_json, LogContext
    
    # One-time setup
    setup_logging_json(log_dir='logs', log_level='DEBUG')
    
    # Get logger for a module
    logger = get_logger('sap_session')
    
    # Log with context
    with LogContext(transaction='VA01', session_id='unique-id'):
        try:
            result = session.set_field('P_MATNR', 'ABC123')
            logger.info("Field set successfully", extra={'field': 'P_MATNR'})
        except Exception as e:
            logger.error(f"Field set failed: {e}", exc_info=True)
    
    # Output to logs/sap_session.log in JSON format
    ```

Reference:
    - Python logging: https://docs.python.org/3/library/logging.html
    - JSON Formatter: Custom implementation in JSONFormatter class
    - Thread-local Storage: contextvars module (Python 3.7+)
    - RotatingFileHandler: https://docs.python.org/3/library/logging.handlers.html
    - Error types: sap/error_handler.py
"""

import logging
import logging.handlers
import json
import sys
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from contextvars import ContextVar

# ============================================================================
# Global Context Variables (Thread-Local Storage)
# ============================================================================

_context_transaction: ContextVar[Optional[str]] = ContextVar(
    'transaction', default=None
)
_context_field_name: ContextVar[Optional[str]] = ContextVar(
    'field_name', default=None
)
_context_session_id: ContextVar[Optional[str]] = ContextVar(
    'session_id', default=None
)
_context_attempt: ContextVar[Optional[int]] = ContextVar(
    'attempt', default=None
)
_context_step: ContextVar[Optional[str]] = ContextVar(
    'step', default=None
)

# Global UI log handler (set by setup_logging_json)
_ui_log_handler: Optional['UILogHandler'] = None


# ============================================================================
# JSON Formatter
# ============================================================================

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging.
    
    Converts LogRecord to JSON with all relevant context, message, and
    exception information. Each log entry is valid JSON on a single line.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.
        
        Args:
            record: LogRecord from logging system
            
        Returns:
            JSON string (single line) with all log context
        """
        # Extract exception info if present
        exc_info = None
        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            if exc_type is not None:
                exc_info = {
                    'type': exc_type.__name__,
                    'message': str(exc_value),
                    'traceback': self.formatException(record.exc_info),
                }
        
        # Build context from contextvars
        context = {
            'transaction': _context_transaction.get(),
            'field_name': _context_field_name.get(),
            'session_id': _context_session_id.get(),
            'attempt': _context_attempt.get(),
            'step': _context_step.get(),
        }
        
        # Remove None values from context
        context = {k: v for k, v in context.items() if v is not None}
        
        # Build log entry
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.pathname,
            'line': record.lineno,
            'function': record.funcName,
            'thread_id': record.thread,
            'thread_name': record.threadName,
            'exception': exc_info,
            'context': context,
            'extra': {
                k: v for k, v in record.__dict__.items()
                if k not in (
                    'name', 'msg', 'args', 'created', 'filename', 'funcName',
                    'levelname', 'levelno', 'lineno', 'module', 'msecs',
                    'message', 'pathname', 'process', 'processName',
                    'relativeCreated', 'thread', 'threadName', 'exc_info',
                    'exc_text', 'stack_info', 'getMessage'
                )
            } if hasattr(record, '__dict__') else {}
        }
        
        # Remove None exception and empty extra dict
        if log_entry['exception'] is None:
            del log_entry['exception']
        if not log_entry['extra']:
            del log_entry['extra']
        
        return json.dumps(log_entry, default=str)


# ============================================================================
# Context Manager for Logging Context
# ============================================================================

class LogContext:
    """Context manager for enriching logs with operation context.
    
    Stores transaction, field, session information in thread-local storage
    so all logs within the context include this information.
    
    Attributes:
        transaction: SAP transaction code (e.g., 'VA01')
        field_name: SAP field name being operated on (e.g., 'P_MATNR')
        session_id: Unique session identifier
        step: Operation step description
        attempt: Attempt number for retries
    
    Example:
        ```python
        with LogContext(transaction='VA01', session_id='session-123'):
            logger.info("Starting operation")
            # All logs within this block include transaction='VA01', session_id='session-123'
        ```
    """
    
    def __init__(
        self,
        transaction: Optional[str] = None,
        field_name: Optional[str] = None,
        session_id: Optional[str] = None,
        step: Optional[str] = None,
        attempt: Optional[int] = None,
    ):
        """Initialize context with operation details.
        
        Args:
            transaction: SAP transaction code
            field_name: Field name
            session_id: Session identifier
            step: Operation step
            attempt: Attempt number
        """
        self.transaction = transaction
        self.field_name = field_name
        self.session_id = session_id
        self.step = step
        self.attempt = attempt
        
        # Store previous values
        self._prev_transaction = None
        self._prev_field_name = None
        self._prev_session_id = None
        self._prev_step = None
        self._prev_attempt = None
    
    def __enter__(self) -> 'LogContext':
        """Enter context and set context variables."""
        # Save previous values
        self._prev_transaction = _context_transaction.get()
        self._prev_field_name = _context_field_name.get()
        self._prev_session_id = _context_session_id.get()
        self._prev_step = _context_step.get()
        self._prev_attempt = _context_attempt.get()
        
        # Set new values (if provided, override previous)
        if self.transaction is not None:
            _context_transaction.set(self.transaction)
        if self.field_name is not None:
            _context_field_name.set(self.field_name)
        if self.session_id is not None:
            _context_session_id.set(self.session_id)
        if self.step is not None:
            _context_step.set(self.step)
        if self.attempt is not None:
            _context_attempt.set(self.attempt)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and restore previous values."""
        # Restore previous values
        _context_transaction.set(self._prev_transaction)
        _context_field_name.set(self._prev_field_name)
        _context_session_id.set(self._prev_session_id)
        _context_step.set(self._prev_step)
        _context_attempt.set(self._prev_attempt)


# ============================================================================
# UI Log Handler (NiceGUI Integration)
# ============================================================================

class UILogHandler(logging.Handler):
    """Logging handler that sends logs to NiceGUI UI element.
    
    Maintains a buffer of recent log entries and sends them to the UI
    via a callback function. Supports color-coding by log level.
    
    Attributes:
        max_entries: Maximum number of log entries to display (default: 100)
        callback: Callable(message: str, level: str) to send logs to UI
    """
    
    # Color codes for log levels (can be used in HTML/CSS)
    LEVEL_COLORS = {
        'DEBUG': '#999999',      # Gray
        'INFO': '#0066CC',       # Blue
        'WARNING': '#FF9900',    # Orange
        'ERROR': '#CC0000',      # Red
        'CRITICAL': '#800000',   # Dark red
    }
    
    def __init__(
        self,
        callback: Optional[Callable[[str, str], None]] = None,
        max_entries: int = 100,
        level: int = logging.INFO,
    ):
        """Initialize UI log handler.
        
        Args:
            callback: Optional async function(message: str, level: str) to send logs to UI.
                     If not provided, logs are buffered but not sent.
            max_entries: Maximum log entries to maintain (default 100)
            level: Minimum log level to forward (default INFO)
        """
        super().__init__(level)
        self.callback = callback
        self.max_entries = max_entries
        self.log_entries: list[Dict[str, Any]] = []
        self._lock = threading.Lock()
    
    def emit(self, record: logging.LogRecord) -> None:
        """Send log entry to UI.
        
        Args:
            record: LogRecord from logging system
        """
        try:
            # Check if record level is sufficient (standard logging behavior)
            if record.levelno < self.level:
                return
            
            msg = self.format(record)
            level = record.levelname
            
            with self._lock:
                # Add entry
                self.log_entries.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'level': level,
                    'message': msg,
                })
                
                # Trim to max entries
                if len(self.log_entries) > self.max_entries:
                    self.log_entries = self.log_entries[-self.max_entries:]
            
            # Send to callback if available
            if self.callback:
                try:
                    # Format message for display
                    display_msg = f"[{record.levelname}] {record.getMessage()}"
                    self.callback(display_msg, level)
                except Exception:
                    # Don't raise exceptions in handler
                    pass
        except Exception:
            # Silently ignore errors in handler
            pass
    
    def get_entries(self) -> list[Dict[str, Any]]:
        """Get all buffered log entries.
        
        Returns:
            List of log entry dictionaries
        """
        with self._lock:
            return list(self.log_entries)
    
    def clear_entries(self) -> None:
        """Clear all buffered log entries."""
        with self._lock:
            self.log_entries.clear()


# ============================================================================
# Logger Setup Functions
# ============================================================================

def setup_logging_json(
    log_dir: str = 'logs',
    log_level: str = 'DEBUG',
    max_bytes: int = 10_000_000,  # 10 MB
    backup_count: int = 5,
    ui_callback: Optional[Callable[[str, str], None]] = None,
) -> UILogHandler:
    """Initialize structured JSON logging system.
    
    Configures:
    - Root logger with DEBUG level
    - Console handler (INFO level, formatted text)
    - Rotating file handler (DEBUG level, JSON format)
    - Optional UI handler (INFO level, for browser display)
    
    All handlers except console use JSON formatter for structured output.
    Rotating files: sap_bridge.log, sap_bridge.log.1, sap_bridge.log.2, etc.
    
    Args:
        log_dir: Directory for log files (created if missing)
        log_level: Logging level as string ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        max_bytes: Max size per log file before rotation (default 10 MB)
        backup_count: Number of backup files to keep (default 5)
        ui_callback: Optional callback(message: str, level: str) for UI integration
        
    Returns:
        UILogHandler instance (for later access to buffered logs)
        
    Raises:
        ValueError: If log_level is invalid
    """
    global _ui_log_handler
    
    # Validate log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers (avoid duplicates)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler (formatted text, INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (rotating, JSON format, DEBUG level)
    json_formatter = JSONFormatter()
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / 'sap_bridge.log',
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)
    
    # UI handler (JSON format, INFO level)
    ui_handler = UILogHandler(
        callback=ui_callback,
        max_entries=100,
        level=logging.INFO,
    )
    ui_handler.setFormatter(json_formatter)
    root_logger.addHandler(ui_handler)
    _ui_log_handler = ui_handler
    
    # Log initialization
    init_logger = logging.getLogger('sap.logging_config')
    init_logger.info(
        "Logging configured",
        extra={
            'log_dir': str(log_path),
            'log_level': log_level,
            'max_bytes': max_bytes,
            'backup_count': backup_count,
        }
    )
    
    return ui_handler


def get_logger(name: str) -> logging.Logger:
    """Get a named logger for a module.
    
    Convenience function to get a logger with consistent naming.
    
    Args:
        name: Logger name (typically module name, e.g., 'sap.session')
        
    Returns:
        Configured Logger instance
        
    Example:
        ```python
        logger = get_logger('sap.session')
        logger.debug("Debug message")
        logger.info("Info message")
        logger.error("Error message", exc_info=True)
        ```
    """
    return logging.getLogger(name)


def get_ui_log_entries(max_count: Optional[int] = None) -> list[Dict[str, Any]]:
    """Get recent UI log entries.
    
    Returns buffered log entries from the UI handler. Useful for
    exporting or displaying logs in the browser.
    
    Args:
        max_count: Optional max number of entries to return (most recent)
        
    Returns:
        List of log entry dictionaries with timestamp, level, message
    """
    if _ui_log_handler is None:
        return []
    
    entries = _ui_log_handler.get_entries()
    if max_count:
        entries = entries[-max_count:]
    
    return entries


def clear_ui_log_entries() -> None:
    """Clear all buffered log entries from UI handler."""
    if _ui_log_handler:
        _ui_log_handler.clear_entries()
