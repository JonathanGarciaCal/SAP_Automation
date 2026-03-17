# System Architecture

## High-Level Diagram

```
┌────────────────────────────────────────────────────────────┐
│                      Windows Machine                       │
│                                                            │
│  ┌──────────┐    COM (win32com)    ┌────────────────────┐  │
│  │ SAP GUI  │◄────────────────────►│   Python Process   │  │
│  │ (32/64b) │                      │                    │  │
│  └──────────┘                      │  ┌──────────────┐  │  │
│                                    │  │ SAP COM      │  │  │
│                                    │  │ Worker Thread│  │  │
│                                    │  │ (CoInit'd)   │  │  │
│                                    │  └──────┬───────┘  │  │
│                                    │         │ Queue    │  │
│                                    │  ┌──────▼───────┐  │  │
│                                    │  │  NiceGUI     │  │  │
│                                    │  │  (FastAPI +  │  │  │
│                                    │  │   asyncio)   │  │  │
│                                    │  └──────┬───────┘  │  │
│                                    └─────────┼──────────┘  │
│                                              │ WebSocket   │
│                                    ┌─────────▼──────────┐  │
│                                    │   Browser Tab      │  │
│                                    │   (localhost:8080)  │  │
│                                    └────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

## Three Execution Contexts

The application has three distinct execution contexts that must never be confused:

### 1. NiceGUI Event Loop (main thread)
- Owns the FastAPI/uvicorn server
- Runs all async coroutines, UI callbacks, and WebSocket communication
- **Must never call COM directly** — blocking COM calls would freeze the UI
- Communicates with the COM thread via queue + asyncio Future

### 2. SAP COM Worker Thread (dedicated background thread)
- Single long-lived `threading.Thread`, started at app launch
- Calls `pythoncom.CoInitialize()` at thread start
- Owns all COM object references (`GuiApplication`, `GuiConnection`, `GuiSession`)
- Runs an internal loop pulling commands from a `queue.Queue`
- Returns results by resolving `asyncio.Future` objects on the main loop
- **Only thread that touches COM objects**

### 3. Browser Client (Vue.js / Quasar)
- Renders the UI from NiceGUI's server-side element tree
- Communicates via WebSocket (socket.io)
- All user events (clicks, inputs) are sent to the server and invoke Python callbacks
- UI updates are pushed from server to client in batches
- No direct SAP interaction — everything goes through the Python server

## Module Decomposition

```
sap_gui_bridge/
├── main.py                  # Entry point: creates NiceGUI app, starts COM thread
├── config.py                # Pydantic settings model, YAML loader
│
├── sap/                     # SAP COM layer — all COM interactions live here
│   ├── __init__.py
│   ├── bridge.py            # SAPBridge class: queue, worker thread, command dispatch
│   ├── connection.py        # Connect, disconnect, reconnect, heartbeat
│   ├── session.py           # Session wrapper: FindById, transaction navigation
│   ├── inspector.py         # Screen element tree walker, field reader
│   ├── grid_reader.py       # GuiGridView data extraction
│   ├── table_reader.py      # GuiTableControl data extraction
│   ├── script_runner.py     # Execute converted Python scripts
│   └── exporter.py          # Report triggering, file export, clipboard extraction
│
├── ui/                      # NiceGUI UI layer — all pages and components
│   ├── __init__.py
│   ├── layout.py            # Shared layout: header, drawer, footer, navigation
│   ├── pages/
│   │   ├── dashboard.py     # Connection status, session info, quick actions
│   │   ├── inspector.py     # Screen element tree + detail panel + table viewer
│   │   ├── scripts.py       # Script library, parameter forms, execution
│   │   ├── reports.py       # Report definitions, trigger, download
│   │   ├── logs.py          # Live log viewer with filtering
│   │   └── settings.py      # Configuration editor
│   └── components/
│       ├── sap_grid.py      # Reusable AG-Grid wrapper for SAP data
│       ├── status_bar.py    # Connection heartbeat indicator
│       ├── sap_dialog.py    # SAP modal dialog relay to browser
│       └── script_form.py   # Dynamic parameter input form
│
├── models/                  # Data models
│   ├── commands.py          # SAPCommand dataclass (for queue communication)
│   ├── session_info.py      # SessionInfo model (system, client, user, transaction)
│   ├── script_def.py        # Script definition model (name, params, path)
│   └── report_def.py        # Report definition model (transaction, variant, fields)
│
├── utils/
│   ├── vbs_converter.py     # VBScript → Python conversion utility
│   ├── filesystem.py        # Safe file writes, timestamped paths
│   └── logging.py           # Dual-sink logging (file + UI)
│
├── scripts/                 # User's SAP automation scripts (Python)
│   ├── example_se16.py
│   └── example_se16.yaml    # Parameter definitions for the script
│
├── config.yaml              # Application configuration
├── reports.yaml             # Report definitions
└── requirements.txt         # Python dependencies
```

## Data Flow Examples

### Example: User clicks "Read Table" in the browser

```
Browser: User clicks "Execute" button
    │
    ▼
NiceGUI: on_click callback fires (async)
    │  calls: result = await sap_bridge.execute('read_grid')
    │
    ▼
SAPBridge.execute(): creates Future, puts SAPCommand on queue
    │
    ▼
COM Worker Thread: pulls command from queue
    │  calls: grid = session.FindById("wnd[0]/usr/.../shell")
    │  loops:  for row in range(grid.RowCount): GetCellValue(...)
    │  resolves Future with extracted data
    │
    ▼
NiceGUI: await returns with data
    │  updates ui.aggrid with new rowData
    │
    ▼
Browser: AG-Grid re-renders with SAP table data
```

### Example: Heartbeat check (every 5 seconds)

```
NiceGUI: ui.timer(5.0, check_heartbeat)
    │
    ▼
check_heartbeat(): result = await sap_bridge.execute('get_status')
    │
    ▼
COM Worker: reads session.Info.Transaction, session.Info.SystemName
    │  returns SessionInfo(alive=True, system="PRD", transaction="SE16")
    │
    ▼
NiceGUI: updates status_label, changes color green/red
    │
    ▼
Browser: Status bar updates in real-time
```
