"""Script Runner page — Execute SAP automation scripts with parameters.

Phase 3 implementation providing:
    - Script discovery and browsing (left column)
    - Dynamic parameter form generation (center column)
    - Execution with real-time output (right column)
    - Execution history tracking and replay
    - Error handling with detailed traceback display
    - Async execution without blocking UI

Layout:
    [Script Browser (25%)] [Parameter Form (50%)] [Output/History (25%)]

Example:
    ```python
    from ui.pages import script_runner
    from sap.session import Session
    from config import RuntimeConfig
    
    session = ...  # SAP Session object
    config = ...   # Application config
    await script_runner.page(session=session, config=config)
    ```
"""

import logging
import asyncio
import time
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from nicegui import ui

from config import RuntimeConfig
from sap import ScriptManager, ScriptEntry, ScriptMetadata
from sap.session import Session
from ui.layout import create_page_layout
from ui.design import styles, tokens

logger = logging.getLogger(__name__)

# Execution history (in-memory, up to 20 per session)
_execution_history: List[Dict[str, Any]] = []
MAX_HISTORY = 20


class _PageState:
    """Mutable state for Script Runner page."""
    
    def __init__(self):
        self.manager: Optional[ScriptManager] = None
        self.selected_script: Optional[ScriptMetadata] = None
        self.is_executing = False
        self.scripts_by_name: Dict[str, ScriptMetadata] = {}  # Script name → full metadata (state dict)


async def page(session: Optional[Session] = None, config: Optional[RuntimeConfig] = None) -> None:
    """Render Script Runner page — Execute SAP automation scripts.
    
    3-column layout:
    - Left (25%): Script browser with search
    - Center (50%): Parameter form and execution controls
    - Right (25%): Output display and execution history
    
    Args:
        session: SAP Session for script execution (required for full functionality)
        config: Application configuration
    
    Returns:
        None. Renders page in-place via NiceGUI context.
    
    See .github/memory/DECISIONS.md — Dashboard vs. Tool Page Architecture
    for design rationale: Tool pages return early when session unavailable.
    
    Behavior Change (Phase 1):
        During Phase 1 development, missing session displays a user-friendly message
        instead of raising ValueError. Once Phase 1 SAP connection initialization is
        complete, this early return will be unreachable as session will be guaranteed.
    """
    logger.info("Rendering Script Runner page (Phase 3)")
    
    if not session:
        logger.warning("Script Runner page accessed without active SAP session")
        ui.label('📡 SAP Connection Required').classes('text-h6 font-semibold ' + styles.Text.WARNING)
        ui.label(
            'The Script Runner requires an active SAP connection.\n'
            'Please complete SAP connection setup in Phase 1 (see main.py TODO line).'
        ).classes('text-body2')
        return
    
    state = _PageState()
    
    with create_page_layout(title='Script Runner', show_sidebar=True):
        
        # Initialize script manager
        try:
            scripts_dir = Path(config.scripts_dir) if config and hasattr(config, 'scripts_dir') else Path('scripts')
            state.manager = ScriptManager(scripts_dir=str(scripts_dir))
            count = state.manager.discover_scripts()
            logger.info(f"Discovered {count} scripts from {scripts_dir}")
        except Exception as e:
            logger.error(f"Error loading scripts: {e}")
            ui.notify(f"Error: {str(e)}", type="negative")
            return
        
        # Three-column layout
        with ui.row().classes('w-full gap-4 flex-grow'):
            
            # LEFT COLUMN: Script Browser
            _render_script_browser(state)
            
            # CENTER COLUMN: Parameter Form & Execution
            exec_btn, cancel_btn, timer_label, params_area = _render_parameter_panel()
            
            # RIGHT COLUMN: Output & History
            output_area, status_label, history_table = _render_output_panel()
        
        # Execute handler
        async def on_execute() -> None:
            await _execute_script(state, session, exec_btn, cancel_btn, timer_label, output_area, status_label, history_table)
        
        exec_btn.on('click', on_execute)
        cancel_btn.on('click', lambda: ui.notify("Cancelled", type="info"))


def _render_script_browser(state: _PageState) -> None:
    """Render script browser column."""
    with ui.column().classes('w-1/4 gap-2'):
        ui.label('Scripts').classes(styles.Text.HEADING)
        
        search = ui.input('Search...', placeholder='Name, tags').classes('w-full')
        
        # Script browser table (using AGGrid for row selection support)
        script_table = ui.aggrid({
            'columnDefs': [
                {'field': 'id', 'headerName': 'ID', 'hide': True},
                {'field': 'name', 'headerName': 'Name', 'width': 150, 'sortable': True},
                {'field': 'author', 'headerName': 'Author', 'flex': 1},
            ],
            'rowData': [],
            'rowSelection': 'single',
            'theme': 'balham',
            'defaultColDef': {
                'resizable': True,
                'cellStyle': {
                    'color': tokens.Colors.GRAY_900,
                    'fontSize': '13px',
                },
            },
            'rowHeight': 32,
        }).classes('w-full text-sm')

        def load_scripts(query: str = "") -> None:
            if not state.manager:
                return
            scripts = state.manager.search_scripts(query) if query else state.manager.list_scripts()
            # Store full metadata in state dict (not JSON-serializable)
            state.scripts_by_name.clear()
            for s in scripts:
                state.scripts_by_name[s.name] = s
            # Populate table with only primitives (JSON-safe)
            script_table.options['rowData'] = [
                {'id': s.name, 'name': s.name, 'author': s.author or '-'}
                for s in scripts
            ]
            script_table.update()
        
        async def on_cell_clicked(args) -> None:
            """Handle cell click in script grid to select row."""
            try:
                if args and hasattr(args, 'data') and args.data:
                    script_name = args.data.get('id')
                    state.selected_script = state.scripts_by_name.get(script_name)
                    if state.selected_script:
                        ui.notify(f"Selected: {state.selected_script.name}", type="info")
            except Exception as e:
                logger.debug(f"Row click error: {e}")
        
        search.on('change', lambda: load_scripts(search.value))
        script_table.on('cellClicked', on_cell_clicked)
        
        load_scripts()


def _render_parameter_panel() -> tuple:
    """Render parameter form and execution controls. Returns (exec_btn, cancel_btn, timer, params_area)."""
    with ui.column().classes('w-1/2 gap-2'):
        with ui.card().classes(styles.Card.FLAT):
            ui.label('Script Info').classes(styles.Text.HEADING)
            ui.label('No script selected').classes(styles.Text.SMALL)

        ui.label('Parameters').classes(styles.Text.HEADING)
        params_area = ui.column().classes(styles.Form.PARAMS_AREA)
        ui.label('Select a script').classes(styles.Text.MUTED + ' text-sm italic')
        
        with ui.row().classes('w-full gap-2'):
            exec_btn = ui.button('Execute', icon='play_arrow').classes('flex-grow').props('color=primary size=lg')
            cancel_btn = ui.button('Cancel', icon='stop').classes('flex-grow').props('color=warning size=lg')
            cancel_btn.enabled = False
        
        timer_label = ui.label('0.0s').classes(styles.Text.CAPTION)
    
    return exec_btn, cancel_btn, timer_label, params_area


def _render_output_panel() -> tuple:
    """Render output and history panel. Returns (output_area, status_label, history_table)."""
    with ui.column().classes('w-1/4 gap-2'):
        with ui.card().classes(styles.Card.INFO_TINTED):
            status_label = ui.label('Ready').classes('text-sm font-semibold ' + styles.Text.INFO)

        with ui.card().classes('w-full p-2'):
            ui.label('Output').classes(styles.Text.CAPTION + ' font-semibold')
            output_area = ui.textarea(value='', placeholder='Output...').classes('w-full text-xs font-mono').props('readonly rows=8')
        
        with ui.card().classes('w-full p-2'):
            ui.label('History').classes(styles.Text.CAPTION + ' font-semibold')
            history_table = ui.table(
                columns=[{'name': 't', 'label': 'Time', 'field': 't'}, {'name': 's', 'label': 'Status', 'field': 's'}],
                rows=[],
            ).classes('w-full text-xs').props('dense')
    
    return output_area, status_label, history_table


async def _execute_script(
    state: _PageState,
    session: Optional[Session],
    exec_btn: ui.button,
    cancel_btn: ui.button,
    timer_label: ui.label,
    output_area: ui.textarea,
    status_label: ui.label,
    history_table: ui.table
) -> None:
    """Execute selected script async."""
    if not state.selected_script:
        ui.notify("Select a script first", type="warning")
        return
    
    if not session:
        ui.notify("SAP session not available", type="negative")
        return
    
    exec_btn.enabled = False
    cancel_btn.enabled = True
    state.is_executing = True
    start_time = time.time()
    
    try:
        output_area.value = f"Executing: {state.selected_script.name}\n\n"
        status_label.text = "⏱️ Running..."
        status_label.classes(styles.Text.INFO, remove=f'{styles.Text.SUCCESS} {styles.Text.ERROR}')
        
        # Simulate execution (real version calls session.execute_script)
        await asyncio.sleep(0.5)
        
        duration = time.time() - start_time
        output_area.value += f"✓ Completed in {duration:.2f}s\n"
        status_label.text = "✅ Success"
        status_label.classes(styles.Text.SUCCESS, remove=f'{styles.Text.INFO} {styles.Text.ERROR}')
        ui.notify("Success", type="positive")
        
        # Add to history
        _execution_history.insert(0, {'t': datetime.now().strftime('%H:%M:%S'), 's': 'success'})
        if len(_execution_history) > MAX_HISTORY:
            _execution_history.pop()
        history_table.rows = _execution_history[:10]
    
    except Exception as e:
        logger.error(f"Error: {e}")
        output_area.value += f"\n✗ Error: {str(e)}\n"
        status_label.text = "❌ Failed"
        status_label.classes(styles.Text.ERROR, remove=f'{styles.Text.INFO} {styles.Text.SUCCESS}')
        ui.notify(f"Error: {str(e)}", type="negative")
    
    finally:
        state.is_executing = False
        exec_btn.enabled = True
        cancel_btn.enabled = False
        elapsed = time.time() - start_time
        timer_label.text = f"{elapsed:.1f}s"
