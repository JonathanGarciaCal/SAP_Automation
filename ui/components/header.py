"""Common header component for all pages.

Displays application title, SAP connection status, user info, and logout button.
Updates connection status every 5 seconds via polling.

Example:
    ```python
    from ui.components import header
    from sap.session import Session
    from config import RuntimeConfig
    
    header.render(
        title='Home',
        session=my_session,
        config=my_config
    )
    ```
"""

import logging
import asyncio
from typing import Optional

from nicegui import ui

from config import RuntimeConfig
from sap.session import Session

logger = logging.getLogger(__name__)


def render(
    title: str = 'Home',
    session: Optional[Session] = None,
    config: Optional[RuntimeConfig] = None
) -> None:
    """Render header component with title, status, user, and logout button.
    
    Displays:
    - App title: "SAP Automation Framework"
    - Current page title (passed as parameter)
    - Connection status indicator (green dot if connected, red if not)
    - Username (from session or config)
    - Logout button (closes session, clears state, redirects to home)
    
    Status is polled every 5 seconds to update the indicator.
    
    Args:
        title: Current page title to display
        session: SAP Session object for connection status and logout
        config: Application configuration for defaults
        
    Example:
        ```python
        render(title='Inspector', session=sap_session, config=config)
        # Output:
        # ┌─ SAP Automation... | Inspector | ● Connected | demo | [Logout] ┐
        ```
    """
    
    logger.debug("Rendering header: title=%s, session=%r", title, session)
    
    # Get username
    username = "Anonymous"
    if session and hasattr(session, '_username'):
        username = session._username
    elif config and config.sap.username:
        username = config.sap.username
    
    with ui.header().classes('bg-blue-700 text-white p-3 shadow-lg'):
        with ui.row().classes('w-full items-center gap-4'):
            
            # App title and page title
            with ui.column().classes('flex-grow'):
                ui.label('SAP Automation Framework').classes('text-h6 font-bold')
                ui.label(f'● {title}').classes('text-subtitle2 text-blue-100')
            
            # Connection status indicator
            status_indicator = ui.label().classes('text-lg')
            
            async def update_status() -> None:
                """Update connection status indicator."""
                if session and hasattr(session, 'is_connected'):
                    try:
                        is_connected = session.is_connected()
                        if is_connected:
                            status_indicator.text = '● Connected'
                            status_indicator.classes('text-green-300', remove='text-red-300')
                        else:
                            status_indicator.text = '● Disconnected'
                            status_indicator.classes('text-red-300', remove='text-green-300')
                    except Exception as e:
                        logger.warning("Failed to check connection status: %s", e)
                        status_indicator.text = '? Unknown'
                        status_indicator.classes('text-yellow-300')
                else:
                    status_indicator.text = '? Unknown'
                    status_indicator.classes('text-yellow-300')
            
            # Initial status update
            try:
                asyncio.create_task(update_status())
            except RuntimeError:
                # No event loop in test context
                pass
            
            # Poll status every 5 seconds
            ui.timer(5.0, lambda: asyncio.create_task(update_status()) if asyncio.get_event_loop().is_running() else None)
            
            # User name
            ui.label(username).classes('text-white font-semibold')
            
            # Logout button
            async def on_logout_click() -> None:
                """Handle logout button click."""
                logger.info("Logout requested for user: %s", username)
                
                try:
                    if session:
                        await session.close()
                        logger.info("Session closed successfully")
                except Exception as e:
                    logger.error("Error closing session during logout: %s", e)
                
                # Clear app state
                from ui.app import get_app_state, set_app_error
                app_state = get_app_state()
                app_state['error'] = None
                app_state['session'] = None
                set_app_error(None)
                
                # Show success notification
                ui.notify('Logged out successfully', type='positive')
                
                # Redirect to home
                ui.navigate('/')
            
            ui.button(
                icon='logout',
                on_click=on_logout_click
            ).props('dense flat color=white')
