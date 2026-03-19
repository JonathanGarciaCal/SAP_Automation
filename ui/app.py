"""NiceGUI application initialization and routing.

Sets up the FastAPI-based NiceGUI server with all routes and WebSocket handlers.

Example:
    ```python
    from config import get_config
    from sap.connection import SAPConnection
    from ui.app import create_app, connect_to_sap
    
    config = get_config()
    conn = SAPConnection(config.sap)
    app = create_app(config, conn)
    session = await connect_to_sap('D00')
    ```
"""

import logging
import asyncio
from typing import Optional, Any
from nicegui import ui

from config import RuntimeConfig
from sap.connection import SAPConnection
from sap.session import Session

logger = logging.getLogger(__name__)


# Global app state for passing to all pages
_app_state = {
    'error': None,
    'operations': [],
    'session': None,
    'config': None,
    'sap_connection': None,
    'connection_lock': None,
}


class AppState:
    """Thread-safe application state container."""
    
    error: Optional[str] = None
    operations: list = []


def create_app(config: RuntimeConfig, connection: Optional[SAPConnection] = None, session: Optional[Session] = None) -> Any:
    """Create and configure NiceGUI app with all routes.
    
    Initializes the NiceGUI application, sets up error handlers, registers
    all page routes, and configures the UI theme.
    
    Args:
        config: Application configuration (RuntimeConfig)
        connection: SAP Connection object (for connect_to_sap calls)
        session: SAP Session object (legacy, for backward compatibility)
        
    Returns:
        NiceGUI app instance (implicitly created by @ui.page decorators)
        
    Raises:
        RuntimeError: If configuration is invalid
        
    Side Effects:
        - Registers routes for home, inspector, script_runner, reports
        - Sets up error handlers for graceful error display
        - Initializes shared UI state (config, session, app_state)
        - Configures NiceGUI theme and styling
    """
    
    logger.info("Creating NiceGUI app with config: %s", config.app.title)
    
    # Store global app state for page handlers
    _app_state['session'] = session
    _app_state['config'] = config
    _app_state['sap_connection'] = connection
    _app_state['connection_lock'] = asyncio.Lock()
    
    # ─────────────────────────────────────────────────────────────────
    # Route: Home Page (/)
    # ─────────────────────────────────────────────────────────────────
    @ui.page('/')
    async def home_page() -> None:
        """Render home page / dashboard."""
        # Configure NiceGUI on first page load
        ui.colors(primary='#1976d2', secondary='#26a69a', accent='#9c27b0')
        ui.page_title(config.app.title)
        
        try:
            from ui.pages import home
            await home.page(session=_app_state.get('session'), config=config)
        except Exception as e:
            logger.exception("Error rendering home page: %s", e)
            _app_state['error'] = f"Failed to load home page: {str(e)}"
            ui.label(f"❌ Error: {str(e)}").classes('text-red-500 text-lg')
    
    # ─────────────────────────────────────────────────────────────────
    # Route: Screen Inspector (/inspector)
    # ─────────────────────────────────────────────────────────────────
    @ui.page('/inspector')
    async def inspector_page() -> None:
        """Render screen inspector page (Phase 2)."""
        if not config.features.enable_screen_inspector:
            ui.label('Screen Inspector not available in this build').classes(
                'text-orange-500 text-lg'
            )
            return
        
        try:
            from ui.pages import inspector
            await inspector.page(session=_app_state.get('session'), config=config)
        except Exception as e:
            logger.exception("Error rendering inspector page: %s", e)
            _app_state['error'] = f"Failed to load inspector: {str(e)}"
            ui.label(f"❌ Error: {str(e)}").classes('text-red-500 text-lg')
    
    # ─────────────────────────────────────────────────────────────────
    # Route: Script Runner (/script-runner)
    # ─────────────────────────────────────────────────────────────────
    @ui.page('/script-runner')
    async def script_runner_page() -> None:
        """Render script runner page (Phase 3)."""
        if not config.features.enable_script_runner:
            ui.label('Script Runner not available in this build').classes(
                'text-orange-500 text-lg'
            )
            return
        
        try:
            from ui.pages import script_runner
            await script_runner.page(session=_app_state.get('session'), config=config)
        except Exception as e:
            logger.exception("Error rendering script runner page: %s", e)
            _app_state['error'] = f"Failed to load script runner: {str(e)}"
            ui.label(f"❌ Error: {str(e)}").classes('text-red-500 text-lg')
    
    # ─────────────────────────────────────────────────────────────────
    # Route: Reports (/reports)
    # ─────────────────────────────────────────────────────────────────
    @ui.page('/reports')
    async def reports_page() -> None:
        """Render reports page (Phase 4)."""
        if not config.features.enable_report_engine:
            ui.label('Report Engine not available in this build').classes(
                'text-orange-500 text-lg'
            )
            return
        
        try:
            from ui.pages import reports
            await reports.page(session=_app_state.get('session'), config=config)
        except Exception as e:
            logger.exception("Error rendering reports page: %s", e)
            _app_state['error'] = f"Failed to load reports: {str(e)}"
            ui.label(f"❌ Error: {str(e)}").classes('text-red-500 text-lg')
    
    logger.info("NiceGUI app created successfully with %d routes", 4)


def get_app_state() -> dict:
    """Get global application state.
    
    Returns:
        Dict with keys: session, config, error, operations
    """
    return _app_state


def set_app_error(error: Optional[str]) -> None:
    """Set application error message to display in next render.
    
    Args:
        error: Error message string or None to clear
    """
    _app_state['error'] = error
    logger.debug("App error set: %s", error)


async def connect_to_sap(system_id: str) -> Session:
    """Connect to SAP using SSO authentication with attach-first strategy.
    
    Thread-safe connection management via asyncio.Lock. Returns existing session
    if already connected; otherwise creates new connection and stores in app state.
    
    Args:
        system_id: SAP system ID (e.g., 'D00', 'P00')
        
    Returns:
        Session object for interacting with SAP
        
    Raises:
        RuntimeError: If connection fails
        ValueError: If system_id is empty
        
    Example:
        ```python
        from ui.app import connect_to_sap
        
        try:
            session = await connect_to_sap('D00')
            await session.start_transaction('VA01')
        except RuntimeError as e:
            ui.notify(f'Connection failed: {str(e)}', type='negative')
        ```
    """
    if not system_id:
        raise ValueError("system_id cannot be empty")
    
    connection_lock = _app_state.get('connection_lock')
    if not connection_lock:
        connection_lock = asyncio.Lock()
        _app_state['connection_lock'] = connection_lock
    
    async with connection_lock:
        # Return existing session if already connected
        existing_session = _app_state.get('session')
        if existing_session and existing_session.is_connected():
            logger.debug("Reusing existing SAP session for system %s", system_id)
            return existing_session
        
        # Otherwise, open new connection
        connection = _app_state.get('sap_connection')
        if not connection:
            raise RuntimeError("SAP Connection not initialized")
        
        try:
            logger.info("Connecting to SAP system %s (SSO)", system_id)
            session = await connection.open(system_id=system_id, use_sso=True)
            
            # Store session in app state
            _app_state['session'] = session
            _app_state['error'] = None
            
            logger.info("Successfully connected to SAP system %s", system_id)
            return session
        
        except Exception as e:
            # Get stage-aware diagnostics
            diagnostics = connection.get_last_connection_diagnostics()
            stage = diagnostics.get('stage', 'unknown')
            error_msg = diagnostics.get('error', str(e))
            
            # Store stage-aware error in app state
            stage_error_msg = f"Connection failed at '{stage}': {error_msg}"
            _app_state['error'] = stage_error_msg
            _app_state['session'] = None
            
            logger.error("Failed to connect to SAP system %s: %s", system_id, stage_error_msg)
            raise RuntimeError(stage_error_msg)


async def disconnect_from_sap() -> None:
    """Disconnect from SAP and clear session state.
    
    Thread-safe disconnection via asyncio.Lock. Safely closes the session
    and clears the app state.
    
    Returns:
        None
        
    Example:
        ```python
        from ui.app import disconnect_from_sap
        
        await disconnect_from_sap()
        ui.notify('Disconnected from SAP', type='positive')
        ```
    """
    connection_lock = _app_state.get('connection_lock')
    if not connection_lock:
        connection_lock = asyncio.Lock()
        _app_state['connection_lock'] = connection_lock
    
    async with connection_lock:
        session = _app_state.get('session')
        if session and session.is_connected():
            try:
                logger.info("Disconnecting from SAP")
                await session.close()
            except Exception as e:
                logger.warning("Error closing session during disconnect: %s", e)
        
        # Clear app state
        _app_state['session'] = None
        _app_state['error'] = None
        
        logger.info("SAP disconnected and app state cleared")
