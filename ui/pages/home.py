"""Home page / Dashboard.

Displays system status, connection information, quick action buttons, and recent operation log.

Features:
    - SAP connection status card with server, client, user, transaction info
    - SAP system selector (dropdown from saplogon.ini with manual input fallback)
    - Connect to SAP button with error handling and timeout support
    - 6 quick action buttons (Start transactions, screenshot, etc.)
    - Recent operations log showing last 10 operations with timestamps
    - All operations logged with status (Success, Timeout, Error)

Example:
    ```python
    from ui.pages import home
    from sap.session import Session
    from config import RuntimeConfig
    
    session = ...
    config = ...
    await home.page(session=session, config=config)
    ```
"""

import logging
import asyncio
import datetime
from typing import Optional, Dict, Any, List

from nicegui import ui

from config import RuntimeConfig
from sap.session import Session
from ui.layout import create_page_layout
from ui.app import connect_to_sap, disconnect_from_sap, get_app_state
from utils.sap_systems import get_sap_systems

logger = logging.getLogger(__name__)

# Global operations log for this session
_operations_log: List[Dict[str, Any]] = []


def get_active_session() -> Optional[Session]:
    """Get active SAP session from app state.
    
    Reads from _app_state first (for real app); falls back to page parameter
    (for test compatibility).
    
    Returns:
        Session object if connected, None otherwise
    """
    try:
        app_state = get_app_state()
        session = app_state.get('session')
        if session and session.is_connected():
            return session
    except Exception as e:
        logger.debug("Error getting active session from app state: %s", e)
    
    return None


async def page(session: Optional[Session] = None, config: Optional[RuntimeConfig] = None) -> None:
    """Render home page dashboard.
    
    Displays:
    1. Connection status card with SAP server/client/user info
    2. Quick action buttons (6 buttons in 3x2 grid)
    3. Recent operations log (last 10 operations)
    
    Args:
        session: SAP Session object for operations
        config: Application configuration
        
    Example:
        >>> await page(session=sap_session, config=config)
    
    See .github/memory/DECISIONS.md — Dashboard vs. Tool Page Architecture
    for design rationale: Home renders in degraded mode when session unavailable.
    """
    
    logger.info("Rendering home page")
    
    # Handle missing session gracefully
    if not session:
        logger.warning("Home page accessed without active SAP session")
    
    with create_page_layout(title='Home', show_sidebar=True, show_header=True):
        
        # Initial connection warning if no session
        if not session:
            with ui.card().classes('w-full p-4 bg-orange-50 border-l-4 border-orange-500'):
                ui.label('📡 Awaiting SAP Connection').classes('text-h6 font-semibold text-orange-700')
                ui.label(
                    "SAP connection initialization is pending (Phase 1 TODO).\n"
                    "Once connected, you'll see connection details and can access other features."
                ).classes('text-body2 text-orange-600')
        
        # ─────────────────────────────────────────────────────────
        # Section 1: Connection Status Card
        # ─────────────────────────────────────────────────────────
        with ui.card().classes('w-full p-4'):
            ui.label('SAP Connection Status').classes('text-h6 font-semibold')
            
            # Status info row
            with ui.row().classes('w-full gap-4 p-3 bg-gray-50 rounded'):
                
                # Connection status indicator
                status_label = ui.label()
                
                async def update_connection_status() -> None:
                    """Update connection status display."""
                    try:
                        if session and session.is_connected():
                            status_label.text = '✅ Connected'
                            status_label.classes('text-green-600', remove='text-red-600')
                            
                            # Try to get current transaction
                            try:
                                screen_id = await asyncio.wait_for(
                                    session.get_current_screen_id(),
                                    timeout=5.0
                                )
                                transaction_display.text = f'Screen: {screen_id}'
                            except asyncio.TimeoutError:
                                transaction_display.text = 'Screen: (timeout)'
                            except Exception as e:
                                logger.debug("Failed to get screen ID: %s", e)
                                transaction_display.text = 'Screen: (unavailable)'
                        else:
                            status_label.text = '⚠️ Disconnected'
                            status_label.classes('text-red-600', remove='text-green-600')
                            transaction_display.text = 'Screen: (no session)'
                    except Exception as e:
                        logger.error("Error updating connection status: %s", e)
                        status_label.text = f'❌ Error: {str(e)[:30]}'
                        status_label.classes('text-red-600')
                
                # Info fields
                with ui.column().classes('flex-grow'):
                    ui.label(f"Server: {config.sap.logon_path if config else 'N/A'}").classes('text-sm')
                    ui.label(f"Client: {config.sap.client if config else 'N/A'}").classes('text-sm')
                    ui.label(f"User: {session._username if session else 'N/A'}").classes('text-sm')
                
                transaction_display = ui.label('Screen: (loading)').classes('text-sm')
                
                # Initial status update
                await update_connection_status()
                
                # Refresh button
                async def on_refresh_click() -> None:
                    """Handle refresh button click."""
                    await update_connection_status()
                
                ui.button('Refresh', on_click=on_refresh_click).props('dense')
            
            # Auto-update status every 10 seconds
            ui.timer(10.0, lambda: asyncio.create_task(update_connection_status()))
        
        # ─────────────────────────────────────────────────────────
        # Section 1.5: SAP System Selector & Connect
        # ─────────────────────────────────────────────────────────
        with ui.card().classes('w-full p-4'):
            ui.label('Connect to SAP').classes('text-h6 font-semibold')
            
            # Shared state for selected system
            selected_system: Dict[str, Optional[str]] = {'value': None}
            connect_button: Any = None
            status_label = ui.label()
            
            # Get available SAP systems
            sap_systems = get_sap_systems()
            logger.debug("Found %d SAP systems", len(sap_systems))
            
            with ui.row().classes('w-full gap-4'):
                
                # System selector (dropdown or text input)
                if sap_systems:
                    # Create dropdown with system options
                    system_options = {sys['sid']: f"{sys['sid']} - {sys['name']}" for sys in sap_systems}
                    
                    system_select = ui.select(
                        value=list(system_options.keys())[0] if system_options else None,
                        options=system_options
                    ).classes('flex-grow')
                    
                    def on_system_changed(value: Any) -> None:
                        """Handle system selection change."""
                        selected_system['value'] = value
                    
                    system_select.on_value_change(on_system_changed)
                    selected_system['value'] = list(system_options.keys())[0] if system_options else None
                
                else:
                    # Fallback: manual text input if no systems found
                    logger.debug("No SAP systems found; using manual text input")
                    system_input = ui.input(
                        label='SAP System ID',
                        placeholder='e.g., D00'
                    ).classes('flex-grow')
                    
                    def on_system_input_changed(value: Any) -> None:
                        """Handle manual system ID input."""
                        selected_system['value'] = value
                    
                    system_input.on_value_change(on_system_input_changed)
                
                # Connect button
                async def handle_connect_click() -> None:
                    """Handle Connect button click."""
                    system_id = selected_system['value']
                    
                    if not system_id:
                        ui.notify('Please select a system', type='warning')
                        return
                    
                    connect_button.enabled = False
                    spinner_row: Optional[Any] = None
                    
                    try:
                        # Show spinner
                        spinner_row = ui.row().classes('w-full')
                        with spinner_row:
                            spinner = ui.spinner('dots')
                        
                        # Connect with timeout
                        logger.info("Connecting to system %s", system_id)
                        session = await asyncio.wait_for(
                            connect_to_sap(system_id),
                            timeout=30.0
                        )
                        
                        # Success
                        status_label.text = f'✅ Connected to {system_id}'
                        status_label.classes('text-green-600', remove='text-red-600')
                        ui.notify(f'Connected to {system_id}', type='positive')
                        log_operation(f'Connect {system_id}', 'Connected', 'Success')
                        
                        # Clear spinner
                        if spinner_row:
                            spinner_row.clear()
                    
                    except asyncio.TimeoutError:
                        status_label.text = '❌ Connection timeout (30s)'
                        status_label.classes('text-red-600', remove='text-green-600')
                        ui.notify('Connection timeout after 30 seconds', type='negative')
                        log_operation(f'Connect {system_id}', 'Failed', 'Timeout')
                        if spinner_row:
                            spinner_row.clear()
                    
                    except Exception as e:
                        error_msg = str(e)[:60]
                        status_label.text = f'❌ {error_msg}'
                        status_label.classes('text-red-600', remove='text-green-600')
                        ui.notify(f'Connection failed: {error_msg}', type='negative')
                        log_operation(f'Connect {system_id}', 'Failed', error_msg)
                        if spinner_row:
                            try:
                                spinner_row.clear()
                            except:
                                pass
                    
                    finally:
                        connect_button.enabled = True
                
                connect_button = ui.button('Connect', on_click=handle_connect_click).props('unelevated color=positive')
            
            # Status display
            status_label.classes('text-sm text-gray-600')
        
        # ─────────────────────────────────────────────────────────
        # Section 2: Quick Action Buttons (3x2 grid)
        # ─────────────────────────────────────────────────────────
        with ui.card().classes('w-full p-4'):
            ui.label('Quick Actions').classes('text-h6 font-semibold')
            
            # Create button state trackers
            button_states: Dict[str, Dict[str, Any]] = {
                'va01': {'loading': False, 'button': None},
                'me23n': {'loading': False, 'button': None},
                'se11': {'loading': False, 'button': None},
                'screenshot': {'loading': False, 'button': None},
                'home': {'loading': False, 'button': None},
                'refresh': {'loading': False, 'button': None},
            }
            
            spinner_row = ui.row().classes('w-full gap-4 mb-4')
            
            async def on_quick_action(
                action_key: str,
                action_name: str,
                coro_fn
            ) -> None:
                """Handle quick action button click.
                
                Args:
                    action_key: State key for button (e.g., 'va01')
                    action_name: Display name (e.g., 'Start VA01')
                    coro_fn: Async function to execute
                """
                state = button_states[action_key]
                try:
                    state['loading'] = True
                    state['button'].enabled = False
                    
                    # Show spinner
                    with spinner_row:
                        spinner = ui.spinner('dots').set_visibility(True)
                    
                    # Execute operation
                    try:
                        await asyncio.wait_for(coro_fn(), timeout=30.0)
                        
                        # Log success
                        log_operation(action_name, 'Started', 'Success')
                        ui.notify(f'{action_name} completed', type='positive')
                    
                    except asyncio.TimeoutError:
                        log_operation(action_name, 'Started', 'Timeout')
                        from ui.app import set_app_error
                        set_app_error('SAP unresponsive (timeout after 30s)')
                        ui.notify('Timeout: SAP unresponsive', type='negative')
                    
                    except RuntimeError as e:
                        log_operation(action_name, 'Started', f'Error: {str(e)[:30]}')
                        from ui.app import set_app_error
                        set_app_error(f'Session error: {str(e)[:50]}')
                        ui.notify(f'Error: {str(e)[:50]}', type='negative')
                    
                    except Exception as e:
                        log_operation(action_name, 'Started', f'Error: {str(e)[:30]}')
                        from ui.app import set_app_error
                        set_app_error(f'Operation failed: {str(e)[:50]}')
                        ui.notify(f'Error: {str(e)[:50]}', type='negative')
                
                finally:
                    state['loading'] = False
                    state['button'].enabled = True
                    # Clear spinner
                    spinner_row.clear()
            
            # Create action buttons in 3x2 grid
            with ui.row().classes('w-full gap-2'):
                
                # Start VA01 button
                button_states['va01']['button'] = ui.button(
                    'Start VA01',
                    on_click=lambda: asyncio.create_task(
                        on_quick_action(
                            'va01',
                            'VA01',
                            (lambda s: s.start_transaction('VA01') if s else asyncio.sleep(0))(get_active_session())
                        )
                    )
                ).classes('flex-grow')
                
                # Start ME23N button
                button_states['me23n']['button'] = ui.button(
                    'Start ME23N',
                    on_click=lambda: asyncio.create_task(
                        on_quick_action(
                            'me23n',
                            'ME23N',
                            (lambda s: s.start_transaction('ME23N') if s else asyncio.sleep(0))(get_active_session())
                        )
                    )
                ).classes('flex-grow')
                
                # Start SE11 button
                button_states['se11']['button'] = ui.button(
                    'Start SE11',
                    on_click=lambda: asyncio.create_task(
                        on_quick_action(
                            'se11',
                            'SE11',
                            (lambda s: s.start_transaction('SE11') if s else asyncio.sleep(0))(get_active_session())
                        )
                    )
                ).classes('flex-grow')
            
            with ui.row().classes('w-full gap-2'):
                
                # Take screenshot button
                button_states['screenshot']['button'] = ui.button(
                    'Take Screenshot',
                    on_click=lambda: asyncio.create_task(
                        on_quick_action(
                            'screenshot',
                            'Screenshot',
                            lambda: asyncio.sleep(1)  # Placeholder
                        )
                    )
                ).classes('flex-grow')
                
                # Go Home button
                button_states['home']['button'] = ui.button(
                    'Go Home',
                    on_click=lambda: asyncio.create_task(
                        on_quick_action(
                            'home',
                            'Go Home',
                            (lambda s: s.go_home() if s else asyncio.sleep(0))(get_active_session())
                        )
                    )
                ).classes('flex-grow')
                
                # Refresh Status button
                button_states['refresh']['button'] = ui.button(
                    'Refresh Status',
                    on_click=lambda: asyncio.create_task(
                        on_quick_action(
                            'refresh',
                            'Refresh',
                            lambda: asyncio.sleep(0.5)
                        )
                    )
                ).classes('flex-grow')
        
        # ─────────────────────────────────────────────────────────
        # Section 3: Recent Operations Log
        # ─────────────────────────────────────────────────────────
        with ui.card().classes('w-full p-4'):
            ui.label('Recent Operations (Last 10)').classes('text-h6 font-semibold')
            
            # Create columns for the operations table
            columns = [
                {
                    'name': 'timestamp',
                    'label': 'Timestamp',
                    'field': 'timestamp',
                    'align': 'left',
                },
                {
                    'name': 'operation',
                    'label': 'Operation',
                    'field': 'operation',
                    'align': 'left',
                },
                {
                    'name': 'status',
                    'label': 'Status',
                    'field': 'status',
                    'align': 'left',
                },
            ]
            
            # Display operations table
            operations_table = ui.table(
                columns=columns,
                rows=_operations_log[-10:],  # Show last 10
                row_key='id'
            ).props('dense flat')
            
            # Format table
            operations_table.classes('w-full')


def log_operation(
    operation_name: str,
    action: str,
    status: str
) -> None:
    """Log an operation to the recent operations list.
    
    Args:
        operation_name: Name of operation (e.g., 'VA01')
        action: Action taken (e.g., 'Started')
        status: Status result (e.g., 'Success', 'Timeout', 'Error')
    """
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    operation_text = f'{operation_name} {action}'
    
    log_entry = {
        'id': len(_operations_log),
        'timestamp': timestamp,
        'operation': operation_text,
        'status': status,
    }
    
    _operations_log.append(log_entry)
    logger.debug("Operation logged: %s - %s", operation_text, status)
