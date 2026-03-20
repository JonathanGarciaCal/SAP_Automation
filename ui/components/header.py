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
from ui.design import styles

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
    username: str = "Anonymous"
    if session and hasattr(session, '_username') and session._username:
        username = session._username
    elif config and config.sap.username:
        username = config.sap.username
    
    with ui.header().classes(styles.Header.CONTAINER):
        with ui.row().classes('w-full items-center gap-4'):

            # App title and page title
            with ui.column().classes('flex-grow'):
                ui.label('SAP Automation Framework').classes(styles.Header.TITLE)
                ui.label(f'● {title}').classes(styles.Header.SUBTITLE)
            
            # Connection status indicator
            status_indicator = ui.label().classes('text-lg')
            
            async def update_status() -> None:
                """Update connection status indicator."""
                if session and hasattr(session, 'is_connected'):
                    try:
                        is_connected = session.is_connected()
                        if is_connected:
                            status_indicator.text = '● Connected'
                            status_indicator.classes(styles.Header.STATUS_CONNECTED, remove=styles.Header.STATUS_DISCONNECTED)
                        else:
                            status_indicator.text = '● Disconnected'
                            status_indicator.classes(styles.Header.STATUS_DISCONNECTED, remove=styles.Header.STATUS_CONNECTED)
                    except Exception as e:
                        logger.warning("Failed to check connection status: %s", e)
                        status_indicator.text = '? Unknown'
                        status_indicator.classes(styles.Header.STATUS_UNKNOWN)
                else:
                    status_indicator.text = '? Unknown'
                    status_indicator.classes(styles.Header.STATUS_UNKNOWN)
            
            # Initial status update (once=True fires after render, keeps NiceGUI slot context)
            ui.timer(0, update_status, once=True)
            
            # Poll status every 5 seconds
            ui.timer(5.0, update_status)
            
            # User name
            ui.label(username).classes(styles.Header.USERNAME)

            # Logout button
            async def on_logout_click() -> None:
                """Handle logout button click."""
                logger.info("Logout requested for user: %s", username)
                
                try:
                    from ui.app import disconnect_from_sap
                    await disconnect_from_sap()
                    logger.info("Disconnected from SAP successfully")
                except Exception as e:
                    logger.error("Error disconnecting from SAP during logout: %s", e)
                
                # Show success notification
                ui.notify('Logged out successfully', type='positive')
                
                # Redirect to home
                ui.navigate.to('/')
            
            ui.button(
                icon='logout',
                on_click=on_logout_click
            ).props(styles.Header.ICON_BUTTON_PROPS)
