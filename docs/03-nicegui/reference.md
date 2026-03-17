# NiceGUI Framework Reference

## Overview

NiceGUI is a Python-based web UI framework built on FastAPI (backend), Vue.js/Quasar (frontend), and socket.io (WebSocket communication). It renders in the browser but all logic runs server-side in Python.

**Official docs**: `https://nicegui.io/documentation`
**GitHub**: `https://github.com/zauberzeug/nicegui`
**Current version**: 3.x

### Key Architecture Points
- Single process, single uvicorn worker
- All UI state maintained on the Python server
- WebSocket pushes updates from server to browser
- User events flow from browser to server via WebSocket
- Built on asyncio — the event loop must never be blocked

---

## Page Routing & Layout

### Multi-page routing
```python
from nicegui import ui

@ui.page('/')
def dashboard():
    ui.label('Dashboard')

@ui.page('/inspector')
def inspector_page():
    ui.label('Screen Inspector')

@ui.page('/scripts')
def scripts_page():
    ui.label('Script Runner')

@ui.page('/reports')
def reports_page():
    ui.label('Report Engine')

@ui.page('/logs')
def logs_page():
    ui.label('Log Viewer')

@ui.page('/settings')
def settings_page():
    ui.label('Settings')

ui.run(title='SAP GUI Bridge', host='127.0.0.1', port=8080, reload=False)
```

### Layout skeleton
```python
from nicegui import ui, app

def create_layout():
    """Shared layout for all pages"""
    with ui.header().classes('bg-primary text-white'):
        ui.button(icon='menu', on_click=lambda: drawer.toggle()).props('flat color=white')
        ui.label('SAP GUI Bridge').classes('text-h6 q-ml-md')
        ui.space()
        status_icon = ui.icon('circle', color='red').classes('q-mr-sm')
        status_label = ui.label('Disconnected')

    with ui.left_drawer(value=True).classes('bg-grey-2') as drawer:
        ui.label('Navigation').classes('text-h6 q-pa-md')
        with ui.column().classes('q-pa-sm'):
            ui.link('Dashboard', '/').classes('text-body1')
            ui.link('Inspector', '/inspector').classes('text-body1')
            ui.link('Scripts', '/scripts').classes('text-body1')
            ui.link('Reports', '/reports').classes('text-body1')
            ui.link('Logs', '/logs').classes('text-body1')
            ui.separator()
            ui.link('Settings', '/settings').classes('text-body1')

    with ui.footer().classes('bg-grey-3 text-grey-8'):
        ui.label('System: --- | User: --- | Transaction: ---')

    return status_icon, status_label
```

---

## Key Components

### ui.aggrid (AG-Grid) — Primary data display
```python
# Basic usage
grid = ui.aggrid({
    'columnDefs': [
        {'headerName': 'Material', 'field': 'MATNR', 'sortable': True, 'filter': True},
        {'headerName': 'Description', 'field': 'MAKTX', 'sortable': True, 'filter': True},
        {'headerName': 'Type', 'field': 'MTART', 'sortable': True, 'filter': True},
    ],
    'rowData': [],
    'defaultColDef': {'resizable': True, 'flex': 1},
    'pagination': True,
    'paginationPageSize': 50,
}).classes('w-full').style('height: 500px')

# Update data dynamically
def update_grid(data: list[dict]):
    grid.options['rowData'] = data
    grid.update()

# Get data from grid (client-side)
async def export_data():
    rows = await grid.get_client_data()
    # rows is a list of dicts
```

### ui.tree — Element hierarchy inspector
```python
tree = ui.tree(
    [
        {'id': 'root', 'label': 'GuiMainWindow (wnd[0])', 'children': [
            {'id': 'tbar0', 'label': 'GuiToolbar (tbar[0])'},
            {'id': 'tbar1', 'label': 'GuiToolbar (tbar[1])'},
            {'id': 'usr', 'label': 'GuiUserArea (usr)', 'children': [
                {'id': 'field1', 'label': 'GuiTextField: txtFIELD1'},
                {'id': 'field2', 'label': 'GuiCTextField: ctxtFIELD2'},
            ]},
        ]},
    ],
    label_key='label',
    on_select=lambda e: handle_node_select(e.value),
).classes('w-full')
```

### ui.timer — Periodic polling
```python
# Heartbeat check every 5 seconds
ui.timer(5.0, check_sap_connection)

# One-shot delayed execution (after page loads)
ui.timer(0, initialize_data, once=True)

# Timer with active flag
timer = ui.timer(2.0, poll_job_status, active=False)
timer.active = True   # Start polling
timer.active = False  # Stop polling
```

### ui.log — Live log viewer
```python
log = ui.log(max_lines=500).classes('w-full h-80')
log.push('Application started')
log.push('Connected to SAP system PRD')
log.push('ERROR: Element not found: wnd[0]/usr/txtMISSING')
```

### ui.dialog — Modal dialog (for SAP popup relay)
```python
async def show_sap_popup(title: str, message: str):
    with ui.dialog() as dialog, ui.card().classes('q-pa-md'):
        ui.label(title).classes('text-h6')
        ui.label(message)
        with ui.row():
            ui.button('OK', on_click=lambda: dialog.submit('ok'))
            ui.button('Cancel', on_click=lambda: dialog.submit('cancel'))
    result = await dialog
    return result  # 'ok' or 'cancel'
```

### ui.notify — Toast notifications
```python
ui.notify('Report exported successfully', type='positive')
ui.notify('SAP session disconnected', type='negative')
ui.notify('Script running...', type='ongoing', timeout=None)
```

### ui.spinner — Loading indicator
```python
spinner = ui.spinner(size='lg')
spinner.visible = False  # Hide initially

# Show during operation
spinner.visible = True
result = await run.io_bound(long_sap_operation)
spinner.visible = False
```

---

## Background Tasks — The Three Patterns

### Pattern 1: `run.io_bound` ★ Best for SAP COM calls
Runs a **synchronous** function in a **thread pool**. Awaitable.

```python
from nicegui import run, ui

def blocking_sap_call(transaction: str) -> dict:
    """This runs in a background thread"""
    # SAP COM calls here
    return {'status': 'ok', 'data': [...]}

async def on_execute_click():
    spinner.visible = True
    try:
        result = await run.io_bound(blocking_sap_call, 'SE16')
        grid.options['rowData'] = result['data']
        grid.update()
        ui.notify('Data loaded', type='positive')
    except Exception as e:
        ui.notify(f'Error: {e}', type='negative')
    finally:
        spinner.visible = False
```

**Important**: `run.io_bound` uses `asyncio.loop.run_in_executor()` with a `ThreadPoolExecutor`. The function you pass must be synchronous (not async). The thread **must** have `pythoncom.CoInitialize()` called if it uses COM.

### Pattern 2: `background_tasks.create` — Fire-and-forget
For tasks you don't need to await inline.

```python
from nicegui import background_tasks

async def long_export_job():
    """Runs independently in the background"""
    data = await run.io_bound(extract_large_dataset)
    await run.io_bound(save_to_excel, data, filepath)
    ui.notify('Export complete! File saved.', type='positive')

# Fire and forget
background_tasks.create(long_export_job())
```

### Pattern 3: `ui.timer` with `once=True` — Deferred execution
For running something after the page has rendered.

```python
@ui.page('/')
def dashboard():
    # Build UI elements first
    spinner = ui.spinner()
    label = ui.label('Loading...')

    async def load_data():
        result = await run.io_bound(get_sap_status)
        spinner.visible = False
        label.text = f'Connected to {result.system}'

    # Run after page renders
    ui.timer(0, load_data, once=True)
```

### ⚠️ Never use `run.cpu_bound` for SAP COM
`run.cpu_bound` spawns a **separate process** via multiprocessing. COM objects cannot be pickled and transferred across processes. It will fail.

---

## State Management & Reactivity

### `@ui.refreshable` — Re-render sections on demand
```python
@ui.refreshable
def session_info_panel():
    info = sap_bridge.get_cached_info()
    with ui.card().classes('w-full'):
        ui.label(f'System: {info.system}').classes('text-bold')
        ui.label(f'Client: {info.client}')
        ui.label(f'User: {info.user}')
        ui.label(f'Transaction: {info.transaction}')

# Render it
session_info_panel()

# Later, when data changes, re-render:
session_info_panel.refresh()
```

### `app.storage` — Per-user storage
```python
from nicegui import app

# Per-user storage (persists across page navigation)
app.storage.user['last_transaction'] = 'SE16'

# Per-session storage (lost on page refresh)
app.storage.tab['temp_data'] = [...]

# General storage (shared across all users)
app.storage.general['app_config'] = {...}
```

### Data binding
```python
# Two-way binding
text_value = ui.input('Transaction Code').bind_value(app.storage.user, 'transaction')
```

---

## Styling

NiceGUI uses Tailwind CSS classes and Quasar props:

```python
# Tailwind classes
ui.label('Hello').classes('text-xl font-bold text-blue-500 q-pa-md')
ui.card().classes('w-full max-w-4xl mx-auto shadow-lg')

# Quasar props
ui.button('Run').props('color=primary icon=play_arrow')
ui.input('Search').props('outlined dense')

# Custom CSS
ui.label('Custom').style('color: #333; font-family: monospace; font-size: 14px')
```

---

## Application Lifecycle

```python
from nicegui import app, ui

# Run code when the app starts
@app.on_startup
async def startup():
    # Initialize SAP bridge
    sap_bridge.start(asyncio.get_event_loop())

# Run code when the app shuts down
@app.on_shutdown
async def shutdown():
    sap_bridge.stop()

# Run code when a client connects
@app.on_connect
async def on_connect():
    print('Client connected')

# Global error handling
@app.on_exception
async def handle_error(e: Exception):
    ui.notify(f'Error: {e}', type='negative')

ui.run(host='127.0.0.1', port=8080, reload=False)
```

**Important**: Set `reload=False` when using threading/COM, because NiceGUI's auto-reload restarts the process and kills background threads.
