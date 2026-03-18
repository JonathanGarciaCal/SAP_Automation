"""Resilience and error handling layer.

Provides:
    - Exception hierarchy for SAP/COM errors (8 classes)
    - Win32COM error translation to user-friendly messages
    - Error classification (transient vs permanent)
    - Context-aware error tracking (transaction, field, step)
    - Retry logic with exponential backoff
    - Error recovery strategies

Architecture:
    The error handler translates raw Win32COM exceptions (pywintypes.com_error)
    into domain-specific exceptions that carry context and user guidance.
    
    Raw COM error → ErrorTranslator → SAPBridgeError subclass + user message
    
    Transient errors (timeouts, RPC failures) support automatic retry with
    exponential backoff. Permanent errors (auth, permissions) fail fast.

Example:
    ```python
    from sap.error_handler import ErrorTranslator, ErrorContext
    
    try:
        # COM operation
        result = session.GetCellValue(0, 0)
    except Exception as e:
        # Translate to domain-specific error
        error = ErrorTranslator.translate_com_error(
            e,
            context=ErrorContext(transaction="VA01", step="read_grid")
        )
        
        # User-friendly message
        user_msg = ErrorTranslator.get_user_message(error)
        print(user_msg)  # "Cannot read grid. Grid structure may have changed."
        
        # Decide retry strategy
        if ErrorTranslator.is_recoverable(error):
            # Retry with backoff
            pass
        else:
            # Fail fast
            raise error
    ```

Reference:
    - Win32COM error codes: doc/04-win32com/reference.md
    - SAP GUI scripting gotchas: doc/02-sap-scripting/security-tools-ids-gotchas.md
    - Architecture patterns: doc/06-architecture/patterns.md
"""

from typing import Any, Awaitable, Optional, Dict, Callable
from enum import Enum
from dataclasses import dataclass, field
import asyncio
import logging
import traceback
import re

logger = logging.getLogger(__name__)


# ============================================================================
# Exception Hierarchy
# ============================================================================

class SAPBridgeError(Exception):
    """Base exception for all SAP bridge errors.
    
    Attributes:
        message: User-friendly error message
        context: ErrorContext with transaction, field, step info
        original_exception: The original Python exception (if any)
        hresult: Win32COM HRESULT code (if COM error)
    """
    
    def __init__(
        self,
        message: str,
        context: Optional["ErrorContext"] = None,
        original_exception: Optional[Exception] = None,
        hresult: Optional[int] = None
    ):
        """Initialize SAP bridge error.
        
        Args:
            message: User-friendly error description
            context: ErrorContext with operation context
            original_exception: Original exception that triggered this
            hresult: Win32COM HRESULT code (if applicable)
        """
        super().__init__(message)
        self.message = message
        self.context = context or ErrorContext()
        self.original_exception = original_exception
        self.hresult = hresult
    
    def __str__(self) -> str:
        """Return formatted error message with context."""
        parts = [self.message]
        if self.context.transaction:
            parts.append(f"Transaction: {self.context.transaction}")
        if self.context.field_name:
            parts.append(f"Field: {self.context.field_name}")
        if self.context.step:
            parts.append(f"Step: {self.context.step}")
        if self.hresult:
            parts.append(f"Code: {hex(self.hresult)}")
        return " | ".join(parts)


class SAPConnectionError(SAPBridgeError):
    """SAP connection failed (e.g., SAP GUI not running, network unreachable)."""
    pass


class SAPTransactionError(SAPBridgeError):
    """Transaction not found or failed to start."""
    pass


class SAPFieldError(SAPBridgeError):
    """Field not found or type mismatch."""
    pass


class SAPTimeoutError(SAPBridgeError):
    """Operation timed out (SAP unresponsive, network lag)."""
    pass


class SAPGridError(SAPBridgeError):
    """Grid extraction failed (structure changed, grid not accessible)."""
    pass


class SAPAuthenticationError(SAPBridgeError):
    """User not authenticated or credentials invalid."""
    pass


class SAPPermissionError(SAPBridgeError):
    """User lacks permission for this transaction/operation."""
    pass


class SAPSessionError(SAPBridgeError):
    """Session disconnected or terminated unexpectedly."""
    pass


# ============================================================================
# Error Context & Classification
# ============================================================================

class ErrorCategory(Enum):
    """Error classification for recovery strategies.
    
    TRANSIENT: Retry likely to help (network issues, timeouts)
    PERMANENT: Retry won't help (permissions, auth, invalid data)
    UNKNOWN: Unknown classification (use cautious retry)
    """
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for error tracking and diagnostics.
    
    Attributes:
        transaction: SAP transaction code (e.g., 'VA01', 'ZSD_CUSTOM')
        field_name: Field name where error occurred (e.g., 'P_MATNR')
        step: Operation step (e.g., 'navigate', 'set_field', 'read_grid')
        session_id: Session ID for tracing across threads
        attempt: Current retry attempt number
        elapsed_ms: Elapsed time in milliseconds
        extra: Additional context (dict)
    """
    transaction: Optional[str] = None
    field_name: Optional[str] = None
    step: Optional[str] = None
    session_id: Optional[str] = None
    attempt: int = 0
    elapsed_ms: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def with_transaction(self, transaction: str) -> "ErrorContext":
        """Return new context with transaction set."""
        self.transaction = transaction
        return self
    
    def with_field(self, field_name: str) -> "ErrorContext":
        """Return new context with field set."""
        self.field_name = field_name
        return self
    
    def with_step(self, step: str) -> "ErrorContext":
        """Return new context with step set."""
        self.step = step
        return self


# ============================================================================
# Win32COM Error Mapping
# ============================================================================

class ErrorTranslator:
    """Translates Win32COM exceptions to domain-specific SAPBridgeErrors.
    
    Maps HRESULT codes and exception messages to appropriate error types
    with user-friendly guidance.
    """
    
    # Win32COM HRESULT codes (common errors)
    COM_ERROR_CODES: Dict[int, Dict[str, Any]] = {
        # RPC / Network errors (transient)
        0x800706BA: {  # RPC_S_SERVER_UNAVAILABLE
            "error_class": SAPTimeoutError,
            "message": "SAP server is temporarily unavailable",
            "hint": "SAP GUI may be unresponsive. Check network and retry.",
            "category": ErrorCategory.TRANSIENT,
        },
        0x80010108: {  # RPC_E_DISCONNECTED
            "error_class": SAPConnectionError,
            "message": "Connection to SAP lost",
            "hint": "Network interrupted or SAP GUI crashed. Reconnect.",
            "category": ErrorCategory.TRANSIENT,
        },
        0x800706BE: {  # RPC_S_CALL_FAILED
            "error_class": SAPTimeoutError,
            "message": "RPC call failed",
            "hint": "Network timeout or SAP unresponsive. Retry.",
            "category": ErrorCategory.TRANSIENT,
        },
        # Access / Permission errors (permanent)
        0x80070005: {  # E_ACCESSDENIED
            "error_class": SAPPermissionError,
            "message": "Access denied",
            "hint": "Check user permissions for this transaction.",
            "category": ErrorCategory.PERMANENT,
        },
        # Type / Interface errors (permanent)
        0x80004001: {  # E_NOTIMPL
            "error_class": SAPFieldError,
            "message": "Operation not supported",
            "hint": "Field or control type may have changed.",
            "category": ErrorCategory.PERMANENT,
        },
        0x80020005: {  # DISP_E_TYPEMISMATCH
            "error_class": SAPFieldError,
            "message": "Type mismatch",
            "hint": "Field type does not match expected type (text vs numeric).",
            "category": ErrorCategory.PERMANENT,
        },
        0x800A01A8: {  # Object required error
            "error_class": SAPFieldError,
            "message": "Field not found",
            "hint": "Field name incorrect or screen structure changed.",
            "category": ErrorCategory.PERMANENT,
        },
        # Timeout errors (transient)
        0x80004004: {  # E_ABORT
            "error_class": SAPTimeoutError,
            "message": "Operation timeout or user cancelled",
            "hint": "SAP took too long to respond. Retry.",
            "category": ErrorCategory.TRANSIENT,
        },
        # Generic errors
        0x80010001: {  # RPC_E_CALL_REJECTED
            "error_class": SAPTimeoutError,
            "message": "SAP call rejected",
            "hint": "SAP GUI busy or overloaded. Retry shortly.",
            "category": ErrorCategory.TRANSIENT,
        },
    }
    
    # Message keyword patterns for error detection
    MESSAGE_PATTERNS: Dict[str, tuple] = {
        r"field not found|cannot find field|field does not exist": (
            SAPFieldError,
            "Field not found in current SAP screen",
            "Field name may be incorrect or screen has changed.",
            ErrorCategory.PERMANENT,
        ),
        r"transaction not found|invalid transaction|transaction failed": (
            SAPTransactionError,
            "Transaction not found or not accessible",
            "Transaction code may be incorrect. Check SAP authorization.",
            ErrorCategory.PERMANENT,
        ),
        r"cannot set.*field|field is read.?only|no write access": (
            SAPFieldError,
            "Cannot modify this field (read-only or protected)",
            "Field is protected. Try a different field or transaction.",
            ErrorCategory.PERMANENT,
        ),
        r"grid.*structure|grid row.*not found|grid column": (
            SAPGridError,
            "Grid structure error",
            "Grid layout may have changed. Update grid specification.",
            ErrorCategory.PERMANENT,
        ),
        r"timeout|timed out": (
            SAPTimeoutError,
            "Operation timed out",
            "SAP took too long. Network may be slow. Retry.",
            ErrorCategory.TRANSIENT,
        ),
        r"not authorized|permission|access.*denied": (
            SAPPermissionError,
            "Operation not authorized",
            "User lacks permission. Check SAP roles.",
            ErrorCategory.PERMANENT,
        ),
        r"invalid password|authentication failed|logon failed": (
            SAPAuthenticationError,
            "Authentication failed",
            "Check username and password.",
            ErrorCategory.PERMANENT,
        ),
        r"session.*closed|session.*disconnected|session.*terminated": (
            SAPSessionError,
            "Session disconnected",
            "SAP session closed unexpectedly. Reconnect.",
            ErrorCategory.TRANSIENT,
        ),
    }
    
    @staticmethod
    def translate_com_error(
        exception: Exception,
        context: Optional[ErrorContext] = None
    ) -> SAPBridgeError:
        """Translate a Win32COM exception to a SAPBridgeError.
        
        Args:
            exception: Original exception (typically pywintypes.com_error)
            context: ErrorContext with operation details
            
        Returns:
            SAPBridgeError subclass with user-friendly message
        """
        context = context or ErrorContext()
        hresult = None
        exception_message = str(exception)
        error_class = SAPBridgeError
        user_message = "Unknown SAP error occurred"
        hint = "Please contact support if issue persists"
        category = ErrorCategory.UNKNOWN
        hresult = None
        
        # Extract HRESULT from pywintypes.com_error if available
        if hasattr(exception, "hresult"):
            hresult = exception.hresult
            if hresult in ErrorTranslator.COM_ERROR_CODES:
                error_info = ErrorTranslator.COM_ERROR_CODES[hresult]
                error_class = error_info["error_class"]
                user_message = error_info["message"]
                hint = error_info["hint"]
                category = error_info["category"]
        
        # Check exception message for keyword patterns
        if not hresult or category == ErrorCategory.UNKNOWN:
            for pattern, (exc_class, msg, hint_text, cat) in ErrorTranslator.MESSAGE_PATTERNS.items():
                if re.search(pattern, exception_message, re.IGNORECASE):
                    error_class = exc_class
                    user_message = msg
                    hint = hint_text
                    category = cat
                    break
        
        # Add hint to message if not already there
        full_message = f"{user_message} ({hint})" if hint else user_message
        
        # Create and return domain-specific error
        error = error_class(
            message=full_message,
            context=context,
            original_exception=exception,
            hresult=hresult
        )
        
        return error
    
    @staticmethod
    def get_user_message(error: SAPBridgeError) -> str:
        """Extract user-friendly message from error.
        
        Args:
            error: SAPBridgeError to extract message from
            
        Returns:
            User-friendly message suitable for UI display
        """
        return str(error.message)
    
    @staticmethod
    def get_recovery_hint(error: SAPBridgeError) -> Optional[str]:
        """Extract recovery/action hint from error.
        
        Args:
            error: SAPBridgeError to extract hint from
            
        Returns:
            Action hint for user, or None
        """
        # Try to extract hint from full message (format: "Message (Hint)")
        message = error.message
        if "(" in message and ")" in message:
            start = message.rfind("(")
            end = message.rfind(")")
            if start < end:
                return message[start + 1:end]
        return None
    
    @staticmethod
    def is_recoverable(error: SAPBridgeError) -> bool:
        """Determine if error is transient/recoverable.
        
        Args:
            error: SAPBridgeError to classify
            
        Returns:
            True if retry likely to help, False for permanent errors
        """
        if isinstance(error, SAPTimeoutError):
            return True
        if isinstance(error, SAPConnectionError):
            return True
        if isinstance(error, SAPSessionError):
            return True
        if isinstance(error, SAPPermissionError):
            return False
        if isinstance(error, SAPAuthenticationError):
            return False
        if isinstance(error, SAPPermissionError):
            return False
        
        # Default to non-recoverable for unknown errors
        return False


# ============================================================================
# Retry & Recovery Strategies
# ============================================================================

class ErrorRecovery:
    """Retry and recovery strategies for transient errors."""
    
    @staticmethod
    def exponential_backoff(attempt: int, base_delay_ms: float = 500.0) -> float:
        """Calculate delay for exponential backoff.
        
        Formula: delay = base_delay * (2 ** attempt)
        
        Args:
            attempt: Retry attempt number (0-based)
            base_delay_ms: Base delay in milliseconds (default: 500)
            
        Returns:
            Delay in milliseconds
            
        Example:
            attempt=0 → 500ms
            attempt=1 → 1000ms
            attempt=2 → 2000ms
            attempt=3 → 4000ms
        """
        return base_delay_ms * (2 ** attempt)
    
    @staticmethod
    def should_retry(
        error: SAPBridgeError,
        attempt: int,
        max_attempts: int = 3
    ) -> bool:
        """Determine if retry should be attempted.
        
        Args:
            error: SAPBridgeError to evaluate
            attempt: Current attempt number (0-based)
            max_attempts: Maximum retry attempts (default: 3)
            
        Returns:
            True if retry should be attempted
        """
        if attempt >= max_attempts:
            return False
        
        return ErrorTranslator.is_recoverable(error)
    
    @staticmethod
    async def retry_async(
        coro: Callable,
        max_attempts: int = 3,
        base_delay_ms: float = 500.0,
        context: Optional[ErrorContext] = None
    ) -> Any:
        """Execute async function with automatic retry on transient errors.
        
        Args:
            coro: Async callable to execute
            max_attempts: Maximum retry attempts (default: 3)
            base_delay_ms: Base backoff delay in ms (default: 500)
            context: ErrorContext to track (optional)
            
        Returns:
            Result from successful execution
            
        Raises:
            SAPBridgeError: If all retries exhausted
            
        Example:
            ```python
            result = await ErrorRecovery.retry_async(
                session.get_field_value('FIELD'),
                max_attempts=3
            )
            ```
        """
        context = context or ErrorContext()
        last_error = None
        
        for attempt in range(max_attempts):
            context.attempt = attempt
            try:
                return await coro()
            except Exception as e:
                # Translate to domain error
                if not isinstance(e, SAPBridgeError):
                    e = ErrorTranslator.translate_com_error(e, context)
                
                last_error = e
                
                if not ErrorRecovery.should_retry(e, attempt, max_attempts):
                    logger.error(
                        f"Permanent error (not retrying): {e}",
                        exc_info=True
                    )
                    raise e
                
                # Calculate backoff and sleep
                delay_ms = ErrorRecovery.exponential_backoff(attempt, base_delay_ms)
                delay_s = delay_ms / 1000.0
                
                logger.warning(
                    f"Transient error (retry in {delay_s:.1f}s, "
                    f"attempt {attempt + 1}/{max_attempts}): {e}"
                )
                
                await asyncio.sleep(delay_s)
        
        if last_error:
            logger.error(
                f"All retries exhausted after {max_attempts} attempts",
                exc_info=last_error
            )
            raise last_error
        
        raise SAPBridgeError("Retry exhausted with unknown error")


# ============================================================================
# Legacy ErrorHandler (for backward compatibility)
# ============================================================================

class ErrorHandler:
    """Legacy error handler for backward compatibility.
    
    Use ErrorTranslator and ErrorRecovery for new code.
    """
    
    def __init__(self, max_retries: int = 3):
        """Initialize error handler.
        
        Args:
            max_retries: Default max retry attempts (default: 3)
        """
        self._max_retries = max_retries
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify an error.
        
        Args:
            error: Exception to classify
            
        Returns:
            ErrorCategory
        """
        if isinstance(error, SAPBridgeError):
            return (
                ErrorCategory.TRANSIENT
                if ErrorTranslator.is_recoverable(error)
                else ErrorCategory.PERMANENT
            )
        
        # Try to translate and classify
        try:
            translated = ErrorTranslator.translate_com_error(error)
            return (
                ErrorCategory.TRANSIENT
                if ErrorTranslator.is_recoverable(translated)
                else ErrorCategory.PERMANENT
            )
        except Exception:
            return ErrorCategory.UNKNOWN
    
    async def retry_async(
        self,
        coro: Callable,
        max_attempts: Optional[int] = None,
        backoff_ms: float = 500.0
    ) -> Any:
        """Execute async operation with retries.
        
        Args:
            coro: Async callable to execute
            max_attempts: Max attempts (default: self._max_retries)
            backoff_ms: Base backoff in milliseconds (default: 500)
            
        Returns:
            Operation result
            
        Raises:
            Exception: If all retries exhausted
        """
        max_attempts = max_attempts or self._max_retries
        return await ErrorRecovery.retry_async(
            coro,
            max_attempts=max_attempts,
            base_delay_ms=backoff_ms
        )
    
    async def recover_session(self, session: Any) -> bool:
        """Attempt to recover a failed session.
        
        Args:
            session: SAP Session object
            
        Returns:
            True if recovery successful
        """
        # Stub for future implementation
        return False
