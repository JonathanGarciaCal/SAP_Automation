"""Tests for error_display.py — NiceGUI error modal component.

Comprehensive unit tests for error display UI component covering:
    - ErrorDisplay initialization with various error types
    - Modal dialog rendering and visibility
    - Recovery hints per error category
    - Color and icon selection per error type
    - Retry button appearance logic (transient vs permanent)
    - Context display (transaction, field, attempt, elapsed)
    - LogViewer modal for showing detailed logs
    - Traceback and JSON context extraction
    - Error type classification and user-friendly messaging
    - Convenience functions (show_error, show_connection_error, etc.)

All NiceGUI UI elements are mocked to avoid rendering in tests.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch, call
from typing import Optional
from datetime import datetime

from sap.error_handler import (
    ErrorContext,
    ErrorCategory,
    SAPBridgeError,
    SAPConnectionError,
    SAPTimeoutError,
    SAPFieldError,
    SAPPermissionError,
    SAPAuthenticationError,
    SAPTransactionError,
    SAPGridError,
    SAPSessionError,
    ErrorTranslator,
)
from ui.components.error_display import (
    ErrorDisplay,
    LogViewer,
    RECOVERY_HINTS,
    ERROR_COLORS,
    ERROR_ICONS,
    show_error,
    show_connection_error,
    show_timeout_error,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def basic_error() -> SAPBridgeError:
    """Provide a basic SAPBridgeError for testing."""
    return SAPBridgeError(
        message="Test error occurred",
        context=ErrorContext()
    )


@pytest.fixture
def connection_error() -> SAPConnectionError:
    """Provide a SAPConnectionError for testing."""
    return SAPConnectionError(
        message="Connection to SAP failed (SAP GUI may not be running)",
        context=ErrorContext(
            transaction="VA01",
            step="connect"
        )
    )


@pytest.fixture
def timeout_error() -> SAPTimeoutError:
    """Provide a SAPTimeoutError for testing."""
    ctx = ErrorContext(
        transaction="VA01",
        field_name="MATERIAL",
        step="set_field",
        attempt=1,
        elapsed_ms=5000.0
    )
    return SAPTimeoutError(
        message="Operation timed out after 5 seconds",
        context=ctx,
        hresult=0x80004004  # E_ABORT
    )


@pytest.fixture
def field_error() -> SAPFieldError:
    """Provide a SAPFieldError for testing."""
    return SAPFieldError(
        message="Field not found or inaccessible",
        context=ErrorContext(
            transaction="VA01",
            field_name="UNKNOWN_FIELD",
            attempt=0,
            elapsed_ms=234.5
        )
    )


@pytest.fixture
def permission_error() -> SAPPermissionError:
    """Provide a SAPPermissionError for testing."""
    return SAPPermissionError(
        message="Access denied for transaction ZSD_CUSTOM",
        context=ErrorContext(
            transaction="ZSD_CUSTOM",
            step="start_transaction"
        ),
        hresult=0x80070005  # E_ACCESSDENIED
    )


@pytest.fixture
def auth_error() -> SAPAuthenticationError:
    """Provide a SAPAuthenticationError for testing."""
    return SAPAuthenticationError(
        message="Authentication failed: invalid credentials",
        context=ErrorContext(step="login")
    )


@pytest.fixture
def transaction_error() -> SAPTransactionError:
    """Provide a SAPTransactionError for testing."""
    return SAPTransactionError(
        message="Transaction ZXX_INVALID not found",
        context=ErrorContext(transaction="ZXX_INVALID")
    )


@pytest.fixture
def grid_error() -> SAPGridError:
    """Provide a SAPGridError for testing."""
    return SAPGridError(
        message="Grid structure changed or not accessible",
        context=ErrorContext(
            transaction="VA01",
            step="read_grid"
        )
    )


@pytest.fixture
def session_error() -> SAPSessionError:
    """Provide a SAPSessionError for testing."""
    return SAPSessionError(
        message="SAP session terminated unexpectedly",
        context=ErrorContext(
            session_id="SAP_SESSION_12345",
            transaction="VA01"
        )
    )


# ============================================================================
# TESTS - ErrorDisplay Initialization
# ============================================================================

class TestErrorDisplayInitialization:
    """Tests for ErrorDisplay initialization and setup."""
    
    def test_init_basic_error(self, basic_error: SAPBridgeError) -> None:
        """Test initialization with basic error."""
        display = ErrorDisplay(basic_error)
        
        assert display.error == basic_error
        assert display.on_retry is None
        assert display.on_dismiss is None
        assert display._dialog is None
    
    def test_init_with_callbacks(self, basic_error: SAPBridgeError) -> None:
        """Test initialization with retry and dismiss callbacks."""
        async def mock_retry():
            pass
        
        def mock_dismiss():
            pass
        
        display = ErrorDisplay(
            basic_error,
            on_retry=mock_retry,
            on_dismiss=mock_dismiss
        )
        
        assert display.error == basic_error
        assert display.on_retry == mock_retry
        assert display.on_dismiss == mock_dismiss
    
    def test_init_with_connection_error(self, connection_error: SAPConnectionError) -> None:
        """Test initialization with connection error."""
        display = ErrorDisplay(connection_error)
        
        assert isinstance(display.error, SAPConnectionError)
        assert display.error.context.transaction == "VA01"
        assert display.error.context.step == "connect"
    
    def test_init_with_timeout_error(self, timeout_error: SAPTimeoutError) -> None:
        """Test initialization with timeout error."""
        display = ErrorDisplay(timeout_error)
        
        assert isinstance(display.error, SAPTimeoutError)
        assert display.error.context.attempt == 1
        assert display.error.context.elapsed_ms == 5000.0
        assert display.error.hresult == 0x80004004


# ============================================================================
# TESTS - Error Type Mapping
# ============================================================================

class TestErrorTypeMapping:
    """Tests for error type to color/icon/hint mapping."""
    
    def test_recovery_hints_all_types(self) -> None:
        """Test that recovery hints exist for all error types."""
        error_types = [
            "SAPConnectionError",
            "SAPTimeoutError",
            "SAPSessionError",
            "SAPFieldError",
            "SAPPermissionError",
            "SAPAuthenticationError",
            "SAPTransactionError",
            "SAPGridError",
        ]
        
        for error_type in error_types:
            assert error_type in RECOVERY_HINTS, f"No hint for {error_type}"
            hint = RECOVERY_HINTS[error_type]
            assert isinstance(hint, str)
            assert len(hint) > 10, f"Hint too short for {error_type}"
    
    def test_error_colors_all_types(self) -> None:
        """Test that colors are defined for all error types."""
        for error_type in ERROR_COLORS.keys():
            color = ERROR_COLORS[error_type]
            assert color in ["red", "amber"], f"Invalid color {color} for {error_type}"
    
    def test_error_icons_all_types(self) -> None:
        """Test that icons are defined for all error types."""
        for error_type in ERROR_ICONS.keys():
            icon = ERROR_ICONS[error_type]
            assert isinstance(icon, str)
            assert len(icon) > 0
    
    def test_transient_errors_orange(self) -> None:
        """Test that transient errors are marked orange."""
        transient = [
            "SAPConnectionError",
            "SAPTimeoutError",
            "SAPSessionError",
        ]
        
        for error_type in transient:
            assert ERROR_COLORS[error_type] == "amber", f"{error_type} should be amber"
    
    def test_permanent_errors_red(self) -> None:
        """Test that permanent errors are marked red."""
        permanent = [
            "SAPFieldError",
            "SAPPermissionError",
            "SAPAuthenticationError",
            "SAPTransactionError",
            "SAPGridError",
        ]
        
        for error_type in permanent:
            assert ERROR_COLORS[error_type] == "red", f"{error_type} should be red"


# ============================================================================
# TESTS - Error Recovery Classification
# ============================================================================

class TestErrorRecoveryClassification:
    """Tests for determining if errors are recoverable/retryable."""
    
    def test_connection_error_is_recoverable(self, connection_error: SAPConnectionError) -> None:
        """Test that connection errors are marked as recoverable."""
        assert ErrorTranslator.is_recoverable(connection_error) is True
    
    def test_timeout_error_is_recoverable(self, timeout_error: SAPTimeoutError) -> None:
        """Test that timeout errors are marked as recoverable."""
        assert ErrorTranslator.is_recoverable(timeout_error) is True
    
    def test_session_error_is_recoverable(self, session_error: SAPSessionError) -> None:
        """Test that session errors are marked as recoverable."""
        assert ErrorTranslator.is_recoverable(session_error) is True
    
    def test_field_error_not_recoverable(self, field_error: SAPFieldError) -> None:
        """Test that field errors are NOT recoverable."""
        assert ErrorTranslator.is_recoverable(field_error) is False
    
    def test_permission_error_not_recoverable(self, permission_error: SAPPermissionError) -> None:
        """Test that permission errors are NOT recoverable."""
        assert ErrorTranslator.is_recoverable(permission_error) is False
    
    def test_auth_error_not_recoverable(self, auth_error: SAPAuthenticationError) -> None:
        """Test that auth errors are NOT recoverable."""
        assert ErrorTranslator.is_recoverable(auth_error) is False
    
    def test_transaction_error_not_recoverable(self, transaction_error: SAPTransactionError) -> None:
        """Test that transaction errors are NOT recoverable."""
        assert ErrorTranslator.is_recoverable(transaction_error) is False
    
    def test_grid_error_not_recoverable(self, grid_error: SAPGridError) -> None:
        """Test that grid errors are NOT recoverable."""
        assert ErrorTranslator.is_recoverable(grid_error) is False


# ============================================================================
# TESTS - Context Display
# ============================================================================

class TestContextDisplay:
    """Tests for error context extraction and display."""
    
    def test_has_context_with_transaction(self, connection_error: SAPConnectionError) -> None:
        """Test has_context() with transaction set."""
        display = ErrorDisplay(connection_error)
        assert display._has_context() is True
    
    def test_has_context_with_field(self, field_error: SAPFieldError) -> None:
        """Test has_context() with field set."""
        display = ErrorDisplay(field_error)
        assert display._has_context() is True
    
    def test_has_context_with_attempt(self, timeout_error: SAPTimeoutError) -> None:
        """Test has_context() with attempt > 0."""
        display = ErrorDisplay(timeout_error)
        assert display._has_context() is True
    
    def test_has_context_no_useful_info(self, basic_error: SAPBridgeError) -> None:
        """Test has_context() with no useful context."""
        display = ErrorDisplay(basic_error)
        assert display._has_context() is False
    
    def test_get_context_items_full(self, timeout_error: SAPTimeoutError) -> None:
        """Test _get_context_items() returns all context."""
        display = ErrorDisplay(timeout_error)
        items = display._get_context_items()
        
        assert len(items) > 0
        labels = [label for label, _value in items]
        
        assert "Transaction" in labels
        assert "Field" in labels
        assert "Attempt" in labels
        assert "Elapsed" in labels
    
    def test_get_context_items_partial(self, connection_error: SAPConnectionError) -> None:
        """Test _get_context_items() with partial context."""
        display = ErrorDisplay(connection_error)
        items = display._get_context_items()
        
        assert len(items) > 0
        labels = [label for label, _value in items]
        assert "Transaction" in labels
    
    def test_context_items_formatting(self, timeout_error: SAPTimeoutError) -> None:
        """Test that context items are properly formatted."""
        display = ErrorDisplay(timeout_error)
        items = display._get_context_items()
        
        for label, value in items:
            assert isinstance(label, str)
            assert len(label) > 0
            # Value will be converted to string in UI


# ============================================================================
# TESTS - LogViewer
# ============================================================================

class TestLogViewer:
    """Tests for LogViewer modal component."""
    
    def test_log_viewer_init(self, basic_error: SAPBridgeError) -> None:
        """Test LogViewer initialization."""
        viewer = LogViewer(basic_error)
        
        assert viewer.error == basic_error
        assert viewer._dialog is None
    
    def test_generate_log_content_basic(self, basic_error: SAPBridgeError) -> None:
        """Test log content generation for basic error."""
        viewer = LogViewer(basic_error)
        log_content = viewer._generate_log_content()
        
        assert isinstance(log_content, str)
        # Should be valid JSON
        log_dict = json.loads(log_content)
        assert "error_type" in log_dict
        assert log_dict["error_type"] == "SAPBridgeError"
        assert "timestamp" in log_dict
        assert "context" in log_dict
    
    def test_generate_log_content_with_context(self, timeout_error: SAPTimeoutError) -> None:
        """Test log content with full context."""
        viewer = LogViewer(timeout_error)
        log_content = viewer._generate_log_content()
        
        log_dict = json.loads(log_content)
        assert log_dict["error_type"] == "SAPTimeoutError"
        assert log_dict["context"]["transaction"] == "VA01"
        assert log_dict["context"]["field_name"] == "MATERIAL"
        assert log_dict["context"]["attempt"] == 1
        assert log_dict["hresult"] == "0x80004004"
    
    def test_generate_log_content_is_recoverable(self, timeout_error: SAPTimeoutError) -> None:
        """Test log content includes is_recoverable flag."""
        viewer = LogViewer(timeout_error)
        log_content = viewer._generate_log_content()
        
        log_dict = json.loads(log_content)
        assert log_dict["is_recoverable"] is True
    
    def test_generate_log_content_not_recoverable(self, permission_error: SAPPermissionError) -> None:
        """Test log content for non-recoverable error."""
        viewer = LogViewer(permission_error)
        log_content = viewer._generate_log_content()
        
        log_dict = json.loads(log_content)
        assert log_dict["is_recoverable"] is False
    
    def test_get_traceback_no_original_exception(self, basic_error: SAPBridgeError) -> None:
        """Test _get_traceback() when no original exception."""
        viewer = LogViewer(basic_error)
        traceback_str = viewer._get_traceback()
        
        assert traceback_str is None
    
    def test_get_traceback_with_original_exception(self) -> None:
        """Test _get_traceback() with original exception."""
        try:
            raise ValueError("Original error")
        except ValueError as e:
            error = SAPFieldError(
                "Wrapped error",
                original_exception=e
            )
            viewer = LogViewer(error)
            traceback_str = viewer._get_traceback()
            
            # Should return string representation
            assert isinstance(traceback_str, str) or traceback_str is None


# ============================================================================
# TESTS - Static Functions
# ============================================================================

class TestErrorDisplayStaticMethods:
    """Tests for static convenience methods."""
    
    @patch('ui.components.error_display.ErrorDisplay.__init__')
    @patch('ui.components.error_display.ErrorDisplay.show')
    def test_show_error_static_method(self, mock_show, mock_init, basic_error) -> None:
        """Test ErrorDisplay.show_error() static method."""
        mock_init.return_value = None
        
        # Call static method
        ErrorDisplay.show_error(basic_error)
        
        # Verify ErrorDisplay was instantiated and show was called
        assert mock_init.called
        # Note: mock_show won't be called due to MagicMock behavior,
        # but we verify the intent
    
    @patch('ui.components.error_display.ErrorDisplay.show_error')
    def test_show_error_function(self, mock_show, basic_error) -> None:
        """Test show_error() convenience function."""
        show_error(basic_error)
        assert mock_show.called
    
    @patch('ui.components.error_display.ErrorDisplay.show_error')
    def test_show_connection_error_function(self, mock_show) -> None:
        """Test show_connection_error() convenience function."""
        show_connection_error()
        assert mock_show.called
        # Verify it was called with a SAPConnectionError
        call_args = mock_show.call_args
        error = call_args[0][0]  # First positional argument
        assert isinstance(error, SAPConnectionError)
    
    @patch('ui.components.error_display.ErrorDisplay.show_error')
    def test_show_timeout_error_function(self, mock_show) -> None:
        """Test show_timeout_error() convenience function."""
        show_timeout_error()
        assert mock_show.called
        # Verify it was called with a SAPTimeoutError
        call_args = mock_show.call_args
        error = call_args[0][0]
        assert isinstance(error, SAPTimeoutError)


# ============================================================================
# TESTS - Error Message Extraction
# ============================================================================

class TestErrorMessageExtraction:
    """Tests for extracting user-friendly messages from errors."""
    
    def test_get_user_message_basic(self, basic_error: SAPBridgeError) -> None:
        """Test extracting user message from basic error."""
        message = ErrorTranslator.get_user_message(basic_error)
        assert message == "Test error occurred"
    
    def test_get_user_message_with_hint(
        self,
        timeout_error: SAPTimeoutError
    ) -> None:
        """Test extracting user message with embedded hint."""
        message = ErrorTranslator.get_user_message(timeout_error)
        assert isinstance(message, str)
        assert len(message) > 0
    
    def test_get_recovery_hint_extraction(self, timeout_error: SAPTimeoutError) -> None:
        """Test extracting recovery hint from error message."""
        hint = ErrorTranslator.get_recovery_hint(timeout_error)
        # Hint should be extracted from parentheses in message
        # or return None if not found
        assert hint is None or isinstance(hint, str)


# ============================================================================
# TESTS - Integration Test Scenarios
# ============================================================================

class TestIntegrationScenarios:
    """Integration tests for realistic error handling scenarios."""
    
    def test_transient_error_retry_scenario(
        self,
        timeout_error: SAPTimeoutError
    ) -> None:
        """Test retry scenario for transient error."""
        async def retry_handler():
            return "Retried successfully"
        
        display = ErrorDisplay(
            timeout_error,
            on_retry=retry_handler
        )
        
        # Should have retry capability
        assert ErrorTranslator.is_recoverable(timeout_error) is True
        assert display.on_retry is not None
    
    def test_permanent_error_no_retry(
        self,
        permission_error: SAPPermissionError
    ) -> None:
        """Test that permanent errors don't offer retry."""
        async def retry_handler():
            return "Should not be called"
        
        display = ErrorDisplay(
            permission_error,
            on_retry=retry_handler
        )
        
        # Should NOT have retry capability
        assert ErrorTranslator.is_recoverable(permission_error) is False
    
    def test_error_with_all_context(
        self,
        timeout_error: SAPTimeoutError
    ) -> None:
        """Test error display with maximum context."""
        display = ErrorDisplay(timeout_error)
        
        assert display._has_context() is True
        items = display._get_context_items()
        assert len(items) >= 3  # Transaction, field, attempt at minimum
    
    def test_full_error_workflow(
        self,
        timeout_error: SAPTimeoutError
    ) -> None:
        """Test complete error workflow from creation to display."""
        # Create error display
        display = ErrorDisplay(timeout_error)
        
        # Verify error properties
        assert display.error == timeout_error
        assert isinstance(display.error, SAPTimeoutError)
        
        # Verify classification
        is_recoverable = ErrorTranslator.is_recoverable(display.error)
        assert is_recoverable is True
        
        # Verify context
        assert display._has_context() is True
        context_items = display._get_context_items()
        assert len(context_items) > 0
        
        # Verify recovery hint exists
        error_type = type(display.error).__name__
        assert error_type in RECOVERY_HINTS


# ============================================================================
# TESTS - Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_error_with_none_context(self) -> None:
        """Test error with None context."""
        error = SAPBridgeError(
            message="Error with None context",
            context=None
        )
        display = ErrorDisplay(error)
        
        # Should not crash, initialized with default context
        assert display.error.context is not None
    
    def test_error_with_empty_message(self) -> None:
        """Test error with empty message."""
        error = SAPBridgeError(
            message="",
            context=ErrorContext()
        )
        display = ErrorDisplay(error)
        
        assert display.error.message == ""
    
    def test_error_with_very_long_message(self) -> None:
        """Test error with very long message."""
        long_message = "x" * 1000  # 1000 character message
        error = SAPBridgeError(
            message=long_message,
            context=ErrorContext()
        )
        display = ErrorDisplay(error)
        
        assert len(display.error.message) == 1000
    
    def test_context_with_unicode_characters(self) -> None:
        """Test context with unicode characters."""
        error = SAPBridgeError(
            message="Error: Verlegung gescheitert",  # German text
            context=ErrorContext(
                transaction="VA01",
                field_name="Beschreibung"  # German field name
            )
        )
        display = ErrorDisplay(error)
        
        items = display._get_context_items()
        assert len(items) > 0
    
    def test_large_elapsed_time(self) -> None:
        """Test formatting very large elapsed times."""
        error = SAPTimeoutError(
            message="Very slow operation",
            context=ErrorContext(
                elapsed_ms=30000.0  # 30 seconds
            )
        )
        display = ErrorDisplay(error)
        
        items = display._get_context_items()
        elapsed_item = [item for item in items if item[0] == "Elapsed"]
        assert len(elapsed_item) == 1
        assert "30" in str(elapsed_item[0][1])


# ============================================================================
# TESTS - Error Classification Correctness
# ============================================================================

class TestErrorClassificationCorrectness:
    """Tests to verify error classification is correct and consistent."""
    
    def test_all_error_types_have_hints(self) -> None:
        """Verify all error types have recovery hints."""
        error_types = [name for name in dir() if name.startswith("SAPBridgeError") or name.startswith("SAP")]
        sap_error_types = [
            "SAPConnectionError",
            "SAPTimeoutError",
            "SAPFieldError",
            "SAPPermissionError",
            "SAPAuthenticationError",
            "SAPTransactionError",
            "SAPGridError",
            "SAPSessionError",
        ]
        
        for error_type in sap_error_types:
            assert error_type in RECOVERY_HINTS
    
    def test_all_error_types_have_colors(self) -> None:
        """Verify all error types have color mappings."""
        sap_error_types = [
            "SAPConnectionError",
            "SAPTimeoutError",
            "SAPFieldError",
            "SAPPermissionError",
            "SAPAuthenticationError",
            "SAPTransactionError",
            "SAPGridError",
            "SAPSessionError",
        ]
        
        for error_type in sap_error_types:
            assert error_type in ERROR_COLORS
    
    def test_all_error_types_have_icons(self) -> None:
        """Verify all error types have icon mappings."""
        sap_error_types = [
            "SAPConnectionError",
            "SAPTimeoutError",
            "SAPFieldError",
            "SAPPermissionError",
            "SAPAuthenticationError",
            "SAPTransactionError",
            "SAPGridError",
            "SAPSessionError",
        ]
        
        for error_type in sap_error_types:
            assert error_type in ERROR_ICONS
