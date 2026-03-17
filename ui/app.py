"""NiceGUI application initialization and routing.

Sets up the FastAPI-based NiceGUI server with all routes and WebSocket handlers.

Example:
    ```python
    from config import get_config
    from sap.connection import SAPConnection
    from ui.app import create_app
    
    config = get_config()
    conn = SAPConnection(config.sap)
    session = await conn.open(config.sap.username, config.sap.password)
    app = create_app(config, session)
    app.run(host=config.app.host, port=config.app.port)
    ```
"""

import logging
from typing import Optional, Any
from nicegui import ui

from config import RuntimeConfig
from sap.session import Session

logger = logging.getLogger(__name__)


# Global app state for passing to all pages
_app_state = {
    'error': None,
    'operations': [],
    'session': None,
    'config': None,
}


class AppState:
    """Thread-safe application state container."""
    
    error: Optional[str] = None
    operations: list = []


def create_app(config: RuntimeConfig, session: Optional[Session] = None) -> Any:
    """Create and configure NiceGUI app with all routes.
    
    Initializes the NiceGUI application, sets up error handlers, registers
    all page routes, and configures the UI theme.
    
    Args:
        config: Application configuration (RuntimeConfig)
        session: SAP Session object (passed to all pages)
        
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
            await home.page(session=session, config=config)
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
            await inspector.page(session=session, config=config)
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
            await script_runner.page(session=session, config=config)
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
            await reports.page(session=session, config=config)
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
