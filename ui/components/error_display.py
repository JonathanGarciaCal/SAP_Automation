"""User-friendly error display UI component.

Provides NiceGUI components for displaying SAP errors in modal dialogs with
context information, recovery hints, retry buttons, and full log viewing.

Features:
    - Error modal dialog with icon, message, and context
    - Color-coded styling per error type (red/orange/yellow)
    - Recovery hints per error category (user-friendly guidance)
    - Retry button shown only for transient/recoverable errors
    - Log viewer modal with full traceback and context JSON
    - Context display: transaction, field, attempt, elapsed time
    - Action buttons: Retry (if transient), View Log, Dismiss

Architecture:
    ErrorDisplay is stateless. It receives an error and optionally a retry
    callback, then renders a modal dialog. The retry callback is invoked
    when user clicks Retry (if error is recoverable).
    
    Color scheme:
    - Connection/Timeout (transient): Orange banner, Retry enabled
    - Field/Permission/Auth (permanent): Red banner, No retry
    - Unknown: Yellow banner, No retry

Example:
    ```python
    from sap.error_handler import ErrorTranslator, ErrorContext, SAPFieldError
    from ui.components.error_display import ErrorDisplay
    
    try:
        field_value = await session.get_field_value('FIELD_NAME')
    except Exception as e:
        error = ErrorTranslator.translate_com_error(
            e,
            context=ErrorContext(transaction='VA01', field_name='FIELD_NAME')
        )
        
        # Show error modal
        async def on_retry():
            field_value = await session.get_field_value('FIELD_NAME')
        
        ErrorDisplay.show_error(error, on_retry=on_retry)
    ```

Reference:
    - Error handler: sap/error_handler.py
    - NiceGUI: https://nicegui.io/
    - Error types: SAPBridgeError, SAPConnectionError, SAPTimeoutError, etc.
"""

import logging
import asyncio
import json
import traceback
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from nicegui import ui

from ui.design import styles
from sap.error_handler import (
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
    ErrorContext,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Recovery Hints Mapping
# ============================================================================

RECOVERY_HINTS: Dict[type, str] = {
    "SAPConnectionError": (
        "SAP GUI may not be running or network is unreachable.\n"
        "• Check if SAP GUI is open and running\n"
        "• Verify network connectivity\n"
        "• Try connecting again in a moment"
    ),
    "SAPTimeoutError": (
        "SAP GUI did not respond in time (network may be slow).\n"
        "• Network latency may be high\n"
        "• SAP server may be temporarily busy\n"
        "• Try the operation again in a moment"
    ),
    "SAPFieldError": (
        "Field could not be found or accessed.\n"
        "• Check if the field name is correct\n"
        "• The SAP screen layout may have changed\n"
        "• Verify you are on the correct transaction"
    ),
    "SAPPermissionError": (
        "You do not have permission for this operation.\n"
        "• Contact your SAP administrator\n"
        "• Your user role may need to be updated\n"
        "• Check transaction authorization in SU01"
    ),
    "SAPAuthenticationError": (
        "Authentication failed (invalid credentials).\n"
        "• Verify your SAP username and password\n"
        "• Your password may have expired\n"
        "• Try logging in to SAP GUI manually to verify credentials"
    ),
    "SAPTransactionError": (
        "Transaction code is invalid or not accessible.\n"
        "• Verify the transaction code is correct\n"
        "• You may not have authorization for this transaction\n"
        "• The transaction may not be available in your SAP system"
    ),
    "SAPGridError": (
        "Failed to read or parse the result grid.\n"
        "• The grid structure may have changed\n"
        "• Try updating your grid column definitions\n"
        "• The SAP system may have been updated"
    ),
    "SAPSessionError": (
        "SAP session was terminated unexpectedly.\n"
        "• Your SAP session may have timed out\n"
        "• SAP GUI may have crashed or closed\n"
        "• Try reconnecting to SAP"
    ),
}


# ============================================================================
# Color & Icon Mapping
# ============================================================================

ERROR_COLORS: Dict[type, str] = {
    "SAPConnectionError": "amber",  # Orange (transient)
    "SAPTimeoutError": "amber",     # Orange (transient)
    "SAPSessionError": "amber",     # Orange (transient)
    "SAPFieldError": "red",         # Red (permanent)
    "SAPPermissionError": "red",    # Red (permanent)
    "SAPAuthenticationError": "red", # Red (permanent)
    "SAPTransactionError": "red",   # Red (permanent)
    "SAPGridError": "red",          # Red (permanent)
}

ERROR_ICONS: Dict[type, str] = {
    "SAPConnectionError": "cloud_off",      # Network/connection icon
    "SAPTimeoutError": "schedule",          # Timeout/clock icon
    "SAPSessionError": "logout",            # Session icon
    "SAPFieldError": "edit_off",            # Field edit disabled
    "SAPPermissionError": "lock",           # Lock icon
    "SAPAuthenticationError": "password",   # Password icon
    "SAPTransactionError": "error",         # Transaction error
    "SAPGridError": "grid_on",              # Grid icon
}


# ============================================================================
# Error Display Component
# ============================================================================

class ErrorDisplay:
    """NiceGUI component for displaying SAP errors in a modal dialog.
    
    Renders a user-friendly error modal with:
    - Error title and icon (color-coded)
    - Main error message
    - Context information (transaction, field, attempt, elapsed time)
    - Recovery hints (per error type)
    - Retry button (if error is recoverable/transient)
    - View Log button (shows full traceback + context)
    - Dismiss button
    
    Attributes:
        error: SAPBridgeError instance being displayed
        on_retry: Optional callback to invoke when user clicks Retry
        on_dismiss: Optional callback to invoke when dialog closes
    """
    
    def __init__(
        self,
        error: SAPBridgeError,
        on_retry: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
    ):
        """Initialize error display component.
        
        Args:
            error: SAPBridgeError to display
            on_retry: Optional async callback when user clicks Retry
            on_dismiss: Optional callback when dialog closes
        """
        self.error = error
        self.on_retry = on_retry
        self.on_dismiss = on_dismiss
        self._dialog: Optional[ui.dialog] = None
        self._retry_button: Optional[ui.button] = None
        self._log_viewer: Optional["LogViewer"] = None
    
    def show(self) -> None:
        """Display error modal dialog.
        
        Renders the error modal with all UI elements and opens it.
        The modal stays open until user clicks Retry, View Log, or Dismiss.
        """
        try:
            self._build_dialog()
            if self._dialog:
                self._dialog.open()
                logger.info(
                    f"Error dialog shown: {type(self.error).__name__}",
                    extra={
                        "error_type": type(self.error).__name__,
                        "transaction": self.error.context.transaction,
                    }
                )
        except Exception as e:
            logger.error(f"Failed to show error dialog: {e}", exc_info=True)
            # Fallback: show notification
            ui.notify(
                f"Error: {str(self.error)[:100]}",
                type="negative",
                position="top"
            )
    
    def _build_dialog(self) -> None:
        """Build the error modal dialog UI.
        
        Constructs the modal with header, message, context, hints, and buttons.
        """
        error_class_name = type(self.error).__name__
        is_recoverable = ErrorTranslator.is_recoverable(self.error)
        color = ERROR_COLORS.get(error_class_name, "red")
        icon = ERROR_ICONS.get(error_class_name, "error")
        
        with ui.dialog() as dialog:
            with ui.card().classes(styles.Modal.CONTAINER):
                
                # ─────────────────────────────────────────────────────────
                # Header section with icon and title
                # ─────────────────────────────────────────────────────────
                with ui.row().classes(f'w-full gap-3 p-4 bg-{color}-50 rounded-t'):
                    ui.icon(icon).classes(f'text-{color}-700 text-2xl')
                    with ui.column().classes('flex-grow'):
                        ui.label('SAP Operation Failed').classes(
                            f'text-{color}-700 text-h6 font-semibold'
                        )
                        ui.label(
                            "An error occurred during the operation"
                        ).classes(styles.Text.SMALL)
                
                # ─────────────────────────────────────────────────────────
                # Main content section
                # ─────────────────────────────────────────────────────────
                with ui.column().classes('gap-3 p-4'):
                    
                    # Error message
                    ui.label('Error:').classes(styles.Text.LABEL)
                    ui.label(self.error.message).classes(
                        styles.Text.BODY + ' whitespace-pre-wrap'
                    )

                    # Recovery hint (if applicable)
                    hint = RECOVERY_HINTS.get(error_class_name)
                    if hint:
                        ui.separator()
                        ui.label('What to do:').classes(styles.Text.LABEL)
                        with ui.row().classes('w-full gap-2'):
                            ui.icon('info').classes(styles.Text.INFO + ' text-lg')
                            ui.label(hint).classes(
                                styles.Text.SMALL + ' whitespace-pre-wrap'
                            )

                    # Context information
                    if self.error.context and self._has_context():
                        ui.separator()
                        ui.label('Context:').classes(styles.Text.LABEL)
                        context_items = self._get_context_items()
                        for label, value in context_items:
                            with ui.row().classes('w-full gap-2'):
                                ui.label(f"• {label}:").classes(
                                    'text-sm font-mono text-gray-600 w-24'
                                )
                                ui.label(str(value)).classes(
                                    styles.Text.MONO + ' flex-grow'
                                )
                
                # ─────────────────────────────────────────────────────────
                # Action buttons
                # ─────────────────────────────────────────────────────────
                with ui.row().classes(styles.Modal.FOOTER):
                    
                    # Retry button (only if error is recoverable)
                    if is_recoverable and self.on_retry:
                        async def handle_retry_click() -> None:
                            """Handle retry button click."""
                            try:
                                logger.info(
                                    f"User clicked Retry on {error_class_name}"
                                )
                                dialog.close()
                                if self.on_retry:
                                    await self.on_retry()
                            except Exception as e:
                                logger.error(f"Retry handler failed: {e}", exc_info=True)
                                ui.notify(
                                    f"Retry failed: {str(e)[:50]}",
                                    type="negative"
                                )
                        
                        self._retry_button = ui.button(
                            'Retry',
                            on_click=handle_retry_click
                        ).props('outline').classes('text-primary')
                    
                    # View Log button
                    def handle_view_log_click() -> None:
                        """Handle View Log button click."""
                        if not self._log_viewer:
                            self._log_viewer = LogViewer(self.error)
                        self._log_viewer.show()
                    
                    ui.button(
                        'View Log',
                        on_click=handle_view_log_click
                    ).props('outline').classes('text-info')
                    
                    # Dismiss button
                    def handle_dismiss_click() -> None:
                        """Handle Dismiss button click."""
                        logger.info(f"User dismissed {error_class_name}")
                        dialog.close()
                        if self.on_dismiss:
                            self.on_dismiss()
                    
                    ui.button(
                        'Dismiss',
                        on_click=handle_dismiss_click
                    ).classes(styles.Text.MUTED)
        
        self._dialog = dialog
    
    def _has_context(self) -> bool:
        """Check if error context has useful information to display.
        
        Returns:
            True if context has transaction, field, attempt, or elapsed_ms
        """
        ctx = self.error.context
        return bool(
            ctx.transaction or ctx.field_name or 
            ctx.attempt > 0 or ctx.elapsed_ms > 0
        )
    
    def _get_context_items(self) -> list:
        """Extract context items for display.
        
        Returns:
            List of (label, value) tuples for context display
        """
        items = []
        ctx = self.error.context
        
        if ctx.transaction:
            items.append(("Transaction", ctx.transaction))
        
        if ctx.field_name:
            items.append(("Field", ctx.field_name))
        
        if ctx.step:
            items.append(("Step", ctx.step))
        
        if ctx.attempt > 0:
            items.append(("Attempt", f"{ctx.attempt} / 3"))
        
        if ctx.elapsed_ms > 0:
            elapsed_s = ctx.elapsed_ms / 1000.0
            items.append(("Elapsed", f"{elapsed_s:.2f}s"))
        
        if ctx.session_id:
            items.append(("Session ID", ctx.session_id[:12]))
        
        return items
    
    @staticmethod
    def show_error(
        error: SAPBridgeError,
        on_retry: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
    ) -> None:
        """Static method to show an error dialog quickly.
        
        Args:
            error: SAPBridgeError to display
            on_retry: Optional async callback for retry
            on_dismiss: Optional callback for dismiss
            
        Example:
            ```python
            try:
                result = await session.get_field()
            except Exception as e:
                error = ErrorTranslator.translate_com_error(e)
                ErrorDisplay.show_error(error, on_retry=async_retry_handler)
            ```
        """
        display = ErrorDisplay(error, on_retry=on_retry, on_dismiss=on_dismiss)
        display.show()


# ============================================================================
# Log Viewer Component
# ============================================================================

class LogViewer:
    """Modal dialog for viewing detailed error logs and traceback.
    
    Displays full error information including:
    - Full error message
    - Exception traceback (if available)
    - Error context as JSON
    - Original exception string
    - Timestamp and HRESULT code (if COM error)
    
    Attributes:
        error: SAPBridgeError to display logs for
    """
    
    def __init__(self, error: SAPBridgeError):
        """Initialize log viewer.
        
        Args:
            error: SAPBridgeError to show logs for
        """
        self.error = error
        self._dialog: Optional[ui.dialog] = None
    
    def show(self) -> None:
        """Display the log viewer dialog.
        
        Renders a modal dialog with scrollable log content and copy button.
        """
        try:
            self._build_dialog()
            if self._dialog:
                self._dialog.open()
                logger.debug("Log viewer dialog opened")
        except Exception as e:
            logger.error(f"Failed to show log viewer: {e}", exc_info=True)
            ui.notify(f"Failed to open log: {str(e)[:50]}", type="negative")
    
    def _build_dialog(self) -> None:
        """Build the log viewer modal."""
        with ui.dialog() as dialog:
            with ui.card().classes(styles.Modal.CONTAINER_LG):

                # Header
                with ui.row().classes(styles.Modal.HEADER_NEUTRAL):
                    ui.label('Error Log Details').classes(styles.Text.HEADING + ' flex-grow')
                    ui.button(
                        icon='close',
                        on_click=lambda: dialog.close()
                    ).props('flat dense')
                
                # Log content (scrollable)
                log_content = self._generate_log_content()
                with ui.scroll_area().classes('w-full flex-grow bg-white'):
                    ui.code(log_content, language='json').classes('w-full text-xs')
                
                # Footer with copy button
                with ui.row().classes(styles.Modal.FOOTER_BORDER):
                    
                    async def copy_to_clipboard() -> None:
                        """Copy log content to clipboard."""
                        try:
                            # Use JavaScript to copy to clipboard (NiceGUI limitation)
                            ui.run_javascript(
                                f"navigator.clipboard.writeText({json.dumps(log_content)})"
                            )
                            ui.notify("Log copied to clipboard", type="positive")
                            logger.debug("Error log copied to clipboard")
                        except Exception as e:
                            logger.warning(f"Failed to copy to clipboard: {e}")
                            ui.notify("Failed to copy", type="warning")
                    
                    ui.button(
                        'Copy',
                        on_click=copy_to_clipboard
                    ).props('outline')
                    
                    ui.button(
                        'Close',
                        on_click=lambda: dialog.close()
                    ).classes(styles.Text.MUTED)
        
        self._dialog = dialog
    
    def _generate_log_content(self) -> str:
        """Generate formatted log content.
        
        Returns:
            JSON string with full error information
        """
        log_dict = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(self.error).__name__,
            "error_message": self.error.message,
            "hresult": hex(self.error.hresult) if self.error.hresult else None,
            "context": {
                "transaction": self.error.context.transaction,
                "field_name": self.error.context.field_name,
                "step": self.error.context.step,
                "session_id": self.error.context.session_id,
                "attempt": self.error.context.attempt,
                "elapsed_ms": self.error.context.elapsed_ms,
                "extra": self.error.context.extra,
            },
            "original_exception": str(self.error.original_exception) if self.error.original_exception else None,
            "traceback": self._get_traceback(),
            "is_recoverable": ErrorTranslator.is_recoverable(self.error),
        }
        
        return json.dumps(log_dict, indent=2, default=str)
    
    def _get_traceback(self) -> Optional[str]:
        """Extract traceback from original exception.
        
        Returns:
            Traceback string or None
        """
        if self.error.original_exception:
            try:
                return traceback.format_exc()
            except Exception:
                return str(self.error.original_exception)
        return None


# ============================================================================
# Convenience Functions
# ============================================================================

def show_error(
    error: SAPBridgeError,
    on_retry: Optional[Callable] = None,
    on_dismiss: Optional[Callable] = None,
) -> None:
    """Show error modal dialog.
    
    Convenience function to show an error without creating ErrorDisplay directly.
    
    Args:
        error: SAPBridgeError to display
        on_retry: Optional async callback for retry
        on_dismiss: Optional callback for dismiss
        
    Example:
        ```python
        from ui.components.error_display import show_error
        from sap.error_handler import ErrorTranslator
        
        try:
            result = await session.get_field('FIELD')
        except Exception as e:
            error = ErrorTranslator.translate_com_error(e)
            show_error(error, on_retry=retry_handler)
        ```
    """
    ErrorDisplay.show_error(error, on_retry=on_retry, on_dismiss=on_dismiss)


def show_connection_error(hint: str = "") -> None:
    """Show connection error notification.
    
    Quick shortcut for connection errors.
    
    Args:
        hint: Optional additional hint message
    """
    error = SAPConnectionError(
        "Failed to connect to SAP. " + (hint or RECOVERY_HINTS["SAPConnectionError"])
    )
    show_error(error)


def show_timeout_error(hint: str = "") -> None:
    """Show timeout error notification.
    
    Quick shortcut for timeout errors.
    
    Args:
        hint: Optional additional hint message
    """
    error = SAPTimeoutError(
        "Operation timed out. " + (hint or RECOVERY_HINTS["SAPTimeoutError"])
    )
    show_error(error)
