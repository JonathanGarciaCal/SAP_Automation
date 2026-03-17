# SAP GUI Bridge — Documentation & Technology Reference

This document compiles all the documentation sources, API references, key concepts, gotchas, and practical patterns needed to build the SAP GUI Bridge application.

---

## 1. SAP GUI Scripting API

### 1.1 Official Documentation Sources

| Document | URL | Notes |
|----------|-----|-------|
| SAP GUI Scripting API (latest, 800) | `https://help.sap.com/doc/9215986e54174174854b0af6bb14305a/800.06/en-US/sap_gui_scripting_api.pdf` | The canonical reference — all objects, methods, properties |
| SAP GUI Scripting API (760) | `https://help.sap.com/doc/9215986e54174174854b0af6bb14305a/760.01/en-US/sap_gui_scripting_api_761.pdf` | Slightly older, but widely deployed version |
| SAP GUI Scripting API (620 — Synactive mirror) | `https://www.synactive.com/download/sap%20gui%20scripting/sap%20gui%20scripting%20api.pdf` | Freely accessible, good for offline reading |
| SAP GUI Scripting Security Guide | `https://help.sap.com/doc/97d2d0bc2ed248a4a85a0bec608704f8/760.01/en-US/sap_gui_scripting_sec_guide.pdf` | All security parameters, per-user control, read-only mode |
| SAP Help Portal — GUI Scripting landing | `https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/` | Official SAP Help entry point |
| SAP Community — Python + GUI Scripting (Stefan Schnell) | `https://community.sap.com/t5/technology-blog-posts-by-members/how-to-use-sap-gui-scripting-inside-python-programming-language/ba-p/13348848` | The seminal blog post: VBScript → Python side-by-side |
| Synactive — GUI Scripting Overview | `https://www.synactive.com/tips/tip_sapguiscripting_2.html` | Practical tips and quick-start |

### 1.2 Object Model Hierarchy

The SAP GUI Scripting API is a tree of COM objects rooted at `GuiApplication`:

```
GuiApplication                          # Root: the SAP GUI process
  └─ GuiConnection[]                    # One per SAP system connection
       └─ GuiSession[]                  # One per window/session
            ├─ GuiSessionInfo            # System name, client, user, transaction
            ├─ GuiMainWindow (wnd[0])    # The primary window
            │   ├─ GuiTitlebar
            │   ├─ GuiToolbar (tbar[0])  # System toolbar (OK code field, Enter, Back…)
            │   ├─ GuiToolbar (tbar[1])  # Application toolbar
            │   ├─ GuiUserArea (usr)     # Main content area — contains all screen fields
            │   │   ├─ GuiTextField (txt...)
            │   │   ├─ GuiCTextField (ctxt...)  # Input fields with F4 help
            │   │   ├─ GuiLabel (lbl...)
            │   │   ├─ GuiButton (btn...)
            │   │   ├─ GuiCheckBox (chk...)
            │   │   ├─ GuiRadioButton (rad...)
            │   │   ├─ GuiComboBox (cmb...)
            │   │   ├─ GuiTableControl (tbl...)  # Classic dynpro tables
            │   │   ├─ GuiCustomControl → GuiContainerShell → GuiGridView (ALV)
            │   │   ├─ GuiTabStrip → GuiTab[]
            │   │   ├─ GuiTree (shell...)
            │   │   ├─ GuiScrollContainer (ssub...)
            │   │   └─ GuiSimpleContainer (sub...)
            │   ├─ GuiMenubar (mbar)
            │   └─ GuiStatusbar (sbar)
            └─ GuiModalWindow (wnd[1])   # Pop-up dialogs
```

**Key interfaces (inherited by most objects)**:
- `GuiComponent` — base: `.Id`, `.Name`, `.Type`, `.Parent`, `.TypeAsNumber`
- `GuiVComponent` — visual: `.Text`, `.Changeable`, `.SetFocus()`, `.Visualize()`
- `GuiVContainer` — container: `.Children`, `.FindById()`, `.FindByName()`, `.FindByNameEx()`
- `GuiContainer` — non-visual container: `.Children`, `.FindById()`

### 1.3 Most Important Objects for the Bridge

#### GuiSession
The central object you interact with most.

**Key properties**:
- `session.Info.SystemName` — SAP system ID (e.g., "PRD")
- `session.Info.Client` — Client number (e.g., "100")
- `session.Info.User` — Logged-in user ID
- `session.Info.Transaction` — Current transaction code
- `session.Info.Program` — Current ABAP program
- `session.Info.Dynpro` — Current screen/dynpro number
- `session.ActiveWindow` — Returns the topmost window (main or modal)
- `session.Busy` — True if SAP is processing a server roundtrip

**Key methods**:
- `session.StartTransaction("SE16")` — Navigate to transaction
- `session.SendCommand("/nSE16")` — Same via OK code (equivalent to typing in command field)
- `session.FindById("wnd[0]/usr/ctxtFIELD")` — Find element by full ID
- `session.CreateSession()` — Open a new SAP session
- `session.EndTransaction()` — End current transaction

#### GuiMainWindow
The primary window: `session.FindById("wnd[0]")`

**Key methods**:
- `window.SendVKey(0)` — Simulate keyboard: 0=Enter, 3=Back, 8=F8 (Execute), 11=Save, 12=Cancel
- `window.Maximize()`, `window.Iconify()`, `window.Restore()`
- `window.ResizeWorkingPane(width, height, false)`

**Complete SendVKey mapping** (critical for automation):
| VKey | Key | Common Use |
|------|-----|------------|
| 0 | Enter | Confirm / Continue |
| 2 | F2 | Double-click equivalent |
| 3 | F3 / Back | Go back |
| 5 | F5 | Execute in some contexts |
| 7 | F7 | Table contents (SE16) |
| 8 | F8 | Execute / Run report |
| 11 | Ctrl+S | Save |
| 12 | F12/Esc | Cancel |
| 24–35 | Ctrl+F1–F12 | Various functions |
| 70 | Ctrl+Shift+F10 | Context menu |
| 71–82 | Ctrl+Shift+F1–F12 | Extended functions |

#### GuiGridView (ALV Grid)
The most complex and important object for data extraction.

**Key properties**:
- `.RowCount` — Total number of rows in the grid
- `.ColumnCount` — Number of columns
- `.VisibleRowCount` — Rows currently visible on screen
- `.FirstVisibleRow` — Index of first visible row (for scrolling)
- `.SelectedRows` — Collection of selected row indices
- `.ColumnOrder` — Array of column technical names

**Key methods**:
- `.GetCellValue(row, columnName)` — Read cell value (row is integer, column is string name)
- `.ModifyCell(row, columnName, value)` — Write to a cell
- `.SetCurrentCell(row, columnName)` — Set cursor position
- `.DoubleClickCurrentCell()` — Double-click the current cell
- `.SelectAll()` — Select all rows
- `.ContextMenu()` — Open right-click menu
- `.PressToolbarButton(buttonId)` — Press an ALV toolbar button
- `.PressToolbarContextButton(buttonId)` — Open a toolbar dropdown

**Scrolling pattern for large data extraction**:
```
total_rows = grid.RowCount
visible = grid.VisibleRowCount
for start in range(0, total_rows, visible):
    grid.FirstVisibleRow = start
    for row in range(start, min(start + visible, total_rows)):
        for col in grid.ColumnOrder:
            value = grid.GetCellValue(row, col)
```

#### GuiTableControl (Classic Dynpro Table)
Older-style table, not ALV. Access pattern is different.

**Key properties**:
- `.RowCount` — Number of visible rows
- `.VerticalScrollbar.Position` — Current scroll position
- `.VerticalScrollbar.Maximum` — Max scroll value
- `.Columns` — Collection of `GuiTableColumn` objects
- `.Rows` — Collection of `GuiTableRow` objects

**Access pattern**:
```
for row_idx in range(table.RowCount):
    row = table.GetAbsoluteRow(row_idx)
    # Access cells through the row's children by column index
```

#### GuiModalWindow
Pop-up dialog: `session.FindById("wnd[1]")`

**Detection pattern** (critical for automation robustness):
```python
active_window = session.ActiveWindow
if active_window.Type == "GuiModalWindow":
    message = session.FindById("wnd[1]/usr/txtMESSTXT1").Text
    # Auto-dismiss: press Enter or a button
    session.FindById("wnd[1]/tbar[0]/btn[0]").Press()
```

### 1.4 VBScript Macro Structure & VBS→Python Conversion

#### Typical recorded VBScript macro structure

SAP's built-in recorder generates `.vbs` files with this pattern:

```vbscript
If Not IsObject(application) Then
   Set SapGuiAuto  = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
If Not IsObject(connection) Then
   Set connection = application.Children(0)
End If
If Not IsObject(session) Then
   Set session    = connection.Children(0)
End If

' --- Actual recorded actions start here ---
session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nSE16"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").text = "MARA"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/txtMAX_SEL").text = "100"
session.findById("wnd[0]/tbar[1]/btn[8]").press
```

#### VBScript → Python conversion rules

| VBScript | Python (win32com) | Notes |
|----------|-------------------|-------|
| `Set obj = GetObject("SAPGUI")` | `obj = win32com.client.GetObject("SAPGUI")` | Remove `Set` |
| `.sendVKey 0` | `.SendVKey(0)` | Add parentheses |
| `.press` | `.Press()` | Add parentheses |
| `.text = "value"` | `.Text = "value"` | Case-insensitive in COM, but capitalize by convention |
| `.select` | `.Select()` | Add parentheses |
| `.setFocus` | `.SetFocus()` | Add parentheses |
| `.caretPosition = 5` | `.CaretPosition = 5` | Direct assignment |
| `True` / `False` | `True` / `False` | Same in Python |
| `If Not IsObject(x) Then` | `if not isinstance(x, win32com.client.CDispatch):` | Type check pattern |
| `session.findById(...)` | `session.FindById(...)` | Same, case-insensitive via COM |

**Minimal Python connection boilerplate** (replace the VBScript preamble):
```python
import win32com.client

SapGui = win32com.client.GetObject("SAPGUI").GetScriptingEngine
session = SapGui.FindById("ses[0]")

# Now use session exactly like VBScript:
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nSE16"
session.FindById("wnd[0]").SendVKey(0)
```

### 1.5 Tools for SAP GUI Scripting Development

#### SAP Built-in Script Recorder
- Access: SAP GUI menu → Customize Local Layout → Script Recording and Playback
- Outputs: `.vbs` files
- Limitations: Only records; no element inspection. Cannot record GuiTree node clicks or GuiGridView cell interactions reliably.

#### Scripting Tracker (Stefan Schnell)
- Download: `https://tracker.stschnell.de/` (retired but still functional)
- Features: Tree-based analyzer showing all scripting objects, a recorder supporting VBScript/PowerShell/Python/AutoIt output, and a Scripting API reference tab
- Current major version: 6 (supports both 32-bit and 64-bit SAP GUI 8.00)
- The Analyzer tab lets you right-click any element → red frame highlights it in SAP → copy its ID
- Note: Creator (Stefan Schnell) retired the project but it still works with modern SAP GUI versions
- Alternative: Load `sapfewse.ocx` (the scripting API COM library) in Excel's Object Browser for type-library browsing

### 1.6 Server-side Security Parameters (Basis Admin Reference)

| Parameter | Value | Effect |
|-----------|-------|--------|
| `sapgui/user_scripting` | `TRUE` | **Required** — enables scripting API |
| `sapgui/user_scripting_per_user` | `TRUE` | Restrict scripting to users with auth object `S_SCR` |
| `sapgui/user_scripting_disable_recording` | `FALSE` | Must be FALSE to allow macro recording |
| `sapgui/user_scripting_set_readonly` | `FALSE` | If TRUE, only read operations allowed (no data changes) |
| `sapgui/user_scripting_force_notification` | `FALSE` | Set FALSE to suppress pop-up notifications about scripting |

Configure via: Transaction `RZ11` (immediate, temporary) or `RZ10` (permanent, requires restart).

### 1.7 Known Limitations & Gotchas

- **No direct database access**: Scripting only drives the GUI. For table reads you must navigate to SE16/SE16N or use ALV grids.
- **Screen-dependent**: Element IDs can change between SAP releases, screen variants, or Enjoy-vs-classic transactions.
- **Modal dialogs block execution**: Any SAP pop-up (info, warning, error) will block until dismissed. Scripts must detect and handle these.
- **ALV grid virtual scrolling**: `GetCellValue()` works for all rows regardless of visibility, but performance degrades on very large datasets. Clipboard extraction (Ctrl+A, Ctrl+C) is faster for 10k+ rows.
- **F4 help pop-ups**: Search help dialogs use a special "Control" mode that scripting cannot fully interact with. Set SAP GUI to "Dialog" mode for F4 help.
- **`sapfewse.ocx` is the COM library**: Located at `C:\Program Files\SAP\FrontEnd\SAPgui\sapfewse.ocx` — this is what `GetObject("SAPGUI")` loads.
- **One GuiApplication per process**: There should only be one SAP GUI scripting engine per Windows user session.

---

## 2. NiceGUI Framework

### 2.1 Official Documentation Sources

| Resource | URL |
|----------|-----|
| NiceGUI Documentation (main) | `https://nicegui.io/documentation` |
| NiceGUI GitHub | `https://github.com/zauberzeug/nicegui` |
| NiceGUI PyPI | `https://pypi.org/project/nicegui/` |
| NiceGUI Wiki / FAQs | `https://github.com/zauberzeug/nicegui/wiki/FAQs` |
| NiceGUI Examples | `https://github.com/zauberzeug/nicegui/tree/main/examples` |
| AG-Grid docs (for ui.aggrid) | `https://nicegui.io/documentation/aggrid` |
| Timer docs | `https://nicegui.io/documentation/timer` |
| Tree docs | `https://nicegui.io/documentation/tree` |
| Run/Background docs | `https://nicegui.io/documentation/run` |
| Action & Events section | `https://nicegui.io/documentation/section_action_events` |
| Data Elements section | `https://nicegui.io/documentation/section_data_elements` |

### 2.2 Architecture Essentials

NiceGUI is built on FastAPI (backend) + Vue.js/Quasar (frontend) + socket.io (WebSocket communication).

- **Single process / single worker** (uvicorn) — no multi-process synchronization needed
- **Backend-first**: All UI logic lives in Python; the framework handles web rendering
- **Server-maintained state**: UI state lives on the Python server, not in the browser
- **Real-time updates**: WebSocket connection sends UI update batches from server to client
- **Event-driven**: User interactions trigger Python callbacks on the server

### 2.3 Key Components for the Bridge

#### Page Routing
```python
from nicegui import ui

@ui.page('/')
def dashboard():
    ui.label('Dashboard')

@ui.page('/inspector')
def inspector():
    ui.label('SAP Screen Inspector')

ui.run(title='SAP GUI Bridge', port=8080)
```

#### Layout Components
```python
# Header + sidebar navigation + footer status bar
with ui.header():
    ui.label('SAP GUI Bridge').classes('text-h6')

with ui.left_drawer() as drawer:
    ui.link('Dashboard', '/')
    ui.link('Inspector', '/inspector')
    ui.link('Scripts', '/scripts')
    ui.link('Reports', '/reports')

with ui.footer():
    status_label = ui.label('Disconnected').classes('text-red')
```

#### ui.aggrid (AG-Grid — primary data display)
```python
grid = ui.aggrid({
    'columnDefs': [
        {'headerName': 'Material', 'field': 'MATNR', 'sortable': True, 'filter': True},
        {'headerName': 'Description', 'field': 'MAKTX', 'sortable': True, 'filter': True},
    ],
    'rowData': [
        {'MATNR': '100001', 'MAKTX': 'Widget A'},
        {'MATNR': '100002', 'MAKTX': 'Widget B'},
    ],
    'defaultColDef': {'resizable': True},
}).classes('w-full h-96')

# Export data from the grid
async def export_csv():
    data = await grid.get_client_data()
    # Process data...
```

#### ui.tree (for element hierarchy inspector)
```python
ui.tree([
    {'id': 'wnd[0]', 'label': 'GuiMainWindow', 'children': [
        {'id': 'wnd[0]/tbar[0]', 'label': 'GuiToolbar (System)'},
        {'id': 'wnd[0]/tbar[1]', 'label': 'GuiToolbar (Application)'},
        {'id': 'wnd[0]/usr', 'label': 'GuiUserArea', 'children': [
            {'id': 'wnd[0]/usr/txtFIELD', 'label': 'GuiTextField: FIELD'},
        ]},
    ]},
], label_key='label', on_select=lambda e: show_details(e.value))
```

#### ui.timer (heartbeat / polling)
```python
def check_connection():
    # Poll SAP session status every 5 seconds
    status = sap_bridge.get_status()
    status_label.text = f'Connected: {status.system}' if status.alive else 'Disconnected'
    status_label.classes(replace='text-green' if status.alive else 'text-red')

ui.timer(5.0, check_connection)
```

#### ui.dialog (for SAP modal dialog relay)
```python
async def show_sap_dialog(message, buttons):
    with ui.dialog() as dialog, ui.card():
        ui.label(message)
        for btn_text, btn_action in buttons:
            ui.button(btn_text, on_click=lambda a=btn_action: (dialog.close(), a()))
    dialog.open()
```

### 2.4 Background Tasks (Critical for COM Integration)

NiceGUI provides three patterns for non-blocking execution:

#### `run.io_bound` — ★ Best fit for SAP COM calls
Runs a synchronous function in a thread pool executor. The COM worker thread must have `CoInitialize()` called.

```python
from nicegui import run, ui

def blocking_sap_call(transaction):
    """This runs in a thread — must have COM initialized"""
    # COM calls happen here
    return result

async def execute_transaction():
    spinner.visible = True
    result = await run.io_bound(blocking_sap_call, 'SE16')
    spinner.visible = False
    ui.notify(f'Result: {result}')
```

#### `background_tasks.create` — Fire-and-forget async tasks
```python
from nicegui import background_tasks

async def long_running_job():
    await run.io_bound(sap_extract_data)
    ui.notify('Extraction complete!')

background_tasks.create(long_running_job())
```

#### `ui.timer` with `once=True` — Deferred execution
```python
ui.timer(0, my_async_function, once=True)  # Runs once, after page renders
```

**Critical warning**: `run.cpu_bound` uses a **separate process** (multiprocessing). COM objects **cannot** be pickled/transferred across processes. **Never use `run.cpu_bound` for SAP COM calls**. Always use `run.io_bound`.

### 2.5 State Management & Reactivity

```python
# ui.refreshable — re-render a section when data changes
@ui.refreshable
def show_session_info():
    info = sap_bridge.session_info
    ui.label(f'System: {info.system}')
    ui.label(f'Transaction: {info.transaction}')
    ui.label(f'User: {info.user}')

show_session_info()

# Later, when data changes:
show_session_info.refresh()
```

### 2.6 Authentication (if needed)
```python
from nicegui import app, ui
from fastapi.responses import RedirectResponse
import starlette.middleware.sessions

app.add_middleware(starlette.middleware.sessions.SessionMiddleware, secret_key='your-secret')

@ui.page('/login')
def login_page():
    # Build login form...
    pass

@ui.page('/')
def main_page():
    if not app.storage.user.get('authenticated'):
        return RedirectResponse('/login')
    # ... build main UI
```

---

## 3. Python win32com / pywin32

### 3.1 Documentation Sources

| Resource | URL |
|----------|-----|
| pywin32 GitHub | `https://github.com/mhammond/pywin32` |
| Quick Start — Client COM | `https://timgolden.me.uk/pywin32-docs/html/com/win32com/HTML/QuickStartClientCom.html` |
| COM threading (CoInitialize) | `https://yiruiscool.wordpress.com/2015/04/29/activate-initialize-com-library-for-calling-thread-in-python/` |
| pywin32 PyPI | `https://pypi.org/project/pywin32/` |

### 3.2 Key Concepts

#### GetObject vs Dispatch
- `win32com.client.GetObject("SAPGUI")` — Attaches to an already-running COM object (SAP GUI must be open)
- `win32com.client.Dispatch("Sapgui.ScriptingCtrl.1")` — Creates a new instance of the COM component

For our project, **always use `GetObject`** — we attach to an existing SAP session.

#### COM Threading Model (most critical for architecture)

COM objects are apartment-threaded. Each thread that uses COM must initialize the COM library:

```python
import pythoncom
import win32com.client
import threading

def sap_worker_thread():
    """Dedicated thread for all SAP COM operations"""
    pythoncom.CoInitialize()  # REQUIRED — initializes COM for this thread
    try:
        SapGui = win32com.client.GetObject("SAPGUI").GetScriptingEngine
        session = SapGui.FindById("ses[0]")
        # ... process commands from queue ...
    finally:
        pythoncom.CoUninitialize()  # Clean up when thread exits

worker = threading.Thread(target=sap_worker_thread, daemon=True)
worker.start()
```

**Rules**:
1. Call `pythoncom.CoInitialize()` at the start of any new thread that uses COM
2. Call `pythoncom.CoUninitialize()` before the thread exits
3. **Never** pass COM object references between threads — the worker thread must own all COM objects
4. Communicate between threads via `queue.Queue` (serializable commands and results)
5. The main thread (NiceGUI's async loop) should never directly touch COM objects

#### Handling COM Errors
```python
import pywintypes

try:
    element = session.FindById("wnd[0]/usr/txtNONEXISTENT")
except pywintypes.com_error as e:
    # e.args = (hresult, description, (source, helpfile, helpcontext, scode), argErr)
    hresult = e.args[0]
    description = e.args[1]
    scode = e.args[2][5] if e.args[2] else None

    # Common error codes:
    # -2147352567 = "Exception occurred" (generic — check inner exception)
    # Error 619 = "The control could not be found by id"
    # Error 614 = "Element not found in collection"
    # Error 605 = "Component could not be instantiated"
```

### 3.3 32-bit vs 64-bit Considerations

- SAP GUI for Windows through version 7.70 is **32-bit only**
- SAP GUI 8.00+ supports **both 32-bit and 64-bit** installations
- **Test first**: Run a 5-line script to validate `GetObject("SAPGUI")` works with your Python bitness
- If using 32-bit SAP GUI with 64-bit Python: `GetObject` may fail with "Class not registered"
- **Safest approach**: Match Python bitness to SAP GUI bitness

---

## 4. Supporting Python Libraries

### 4.1 asyncio + threading integration

The core pattern for bridging NiceGUI's async loop with the COM worker thread:

```python
import asyncio
import queue
import threading
from dataclasses import dataclass
from typing import Any

@dataclass
class SAPCommand:
    method: str
    args: tuple
    future: asyncio.Future

class SAPBridge:
    def __init__(self):
        self._queue = queue.Queue()
        self._loop = None

    def start(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        thread = threading.Thread(target=self._worker, daemon=True)
        thread.start()

    def _worker(self):
        """Runs in dedicated COM thread"""
        import pythoncom
        pythoncom.CoInitialize()
        try:
            sap = win32com.client.GetObject("SAPGUI").GetScriptingEngine
            self._session = sap.FindById("ses[0]")
            while True:
                cmd = self._queue.get()
                try:
                    result = getattr(self, f'_do_{cmd.method}')(*cmd.args)
                    self._loop.call_soon_threadsafe(cmd.future.set_result, result)
                except Exception as e:
                    self._loop.call_soon_threadsafe(cmd.future.set_exception, e)
        finally:
            pythoncom.CoUninitialize()

    async def execute(self, method: str, *args) -> Any:
        """Called from NiceGUI's async context"""
        future = self._loop.create_future()
        self._queue.put(SAPCommand(method, args, future))
        return await future
```

### 4.2 Key Libraries

| Library | Purpose | Install | Documentation |
|---------|---------|---------|---------------|
| `pywin32` | COM automation | `pip install pywin32` | `https://github.com/mhammond/pywin32` |
| `nicegui` | Web UI framework | `pip install nicegui` | `https://nicegui.io/documentation` |
| `pydantic` | Config validation | `pip install pydantic` | `https://docs.pydantic.dev/latest/` |
| `pyyaml` | YAML config files | `pip install pyyaml` | `https://pyyaml.org/wiki/PyYAMLDocumentation` |
| `openpyxl` | Excel file creation | `pip install openpyxl` | `https://openpyxl.readthedocs.io/` |
| `pandas` | Data manipulation | `pip install pandas` | `https://pandas.pydata.org/docs/` |
| `loguru` | Better logging | `pip install loguru` | `https://loguru.readthedocs.io/` |

### 4.3 openpyxl (Excel Export)
```python
from openpyxl import Workbook

def export_to_excel(data: list[dict], filepath: str):
    wb = Workbook()
    ws = wb.active
    if data:
        ws.append(list(data[0].keys()))  # Header row
        for row in data:
            ws.append(list(row.values()))
    wb.save(filepath)
```

### 4.4 win32clipboard (Clipboard Extraction)
For fast extraction from large ALV grids:
```python
import win32clipboard

def get_clipboard_text() -> str:
    win32clipboard.OpenClipboard()
    try:
        data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        return data
    finally:
        win32clipboard.CloseClipboard()

# Usage: after sending Ctrl+A, Ctrl+C to SAP grid
# session.FindById("wnd[0]/usr/cntlGRID/shellcont/shell").SelectAll()
# session.FindById("wnd[0]").SendVKey(24)  # Ctrl+C (VKey 24 = Ctrl+C in some contexts)
```

### 4.5 PyInstaller (Packaging)
```bash
pip install pyinstaller
pyinstaller --onefile --name SAP_Bridge --hidden-import win32com --hidden-import pythoncom main.py
```

---

## 5. SAP-Specific Python Libraries

### 5.1 PySapGUI
- PyPI: `https://pypi.org/project/PySapGUI/`
- A thin wrapper around win32com for SAP GUI Scripting
- Provides convenience methods but adds limited value over raw win32com
- May be useful as reference code but not a hard dependency

### 5.2 PyRFC (Complementary Approach)
- GitHub: `https://github.com/SAP-archive/PyRFC` (archived but still works)
- PyPI: `https://pypi.org/project/pyrfc/`
- Docs: `https://pyrfc.readthedocs.io/`
- Provides **direct RFC calls** to SAP — bypasses the GUI entirely
- Can call `RFC_READ_TABLE` to read any table without navigating to SE16
- **Requires**: SAP NetWeaver RFC SDK (download from SAP Software Download Center, needs S-user)
- **Advantages over GUI scripting**: Faster, more reliable, no screen dependency
- **Disadvantages**: Requires RFC SDK installation, separate authentication, different SAP authorizations
- **Recommendation**: Consider as a Phase 2 enhancement for data extraction tasks. GUI scripting is needed regardless for screen interaction and report execution.

#### Basic PyRFC usage
```python
from pyrfc import Connection

conn = Connection(user='USER', passwd='PASS', ashost='10.0.0.1', sysnr='00', client='100')

# Read a table
result = conn.call('RFC_READ_TABLE',
    QUERY_TABLE='MARA',
    DELIMITER='|',
    FIELDS=[{'FIELDNAME': 'MATNR'}, {'FIELDNAME': 'MTART'}],
    OPTIONS=[{'TEXT': "MTART EQ 'FERT'"}],
    ROWCOUNT=100
)

for row in result['DATA']:
    print(row['WA'].split('|'))

conn.close()
```

### 5.3 RoboSAPiens / robotframework-robosapiens
- PyPI: `https://pypi.org/project/robotframework-robosapiens/`
- Provides a uniform API for all tabular components (GuiGridView, GuiTableControl, GuiTree)
- Addresses cells using column titles and row numbers/text — more robust than raw IDs
- Worth examining for its approach to grid traversal, but adds Robot Framework dependency

---

## 6. Architecture Patterns

### 6.1 Producer-Consumer Pattern (COM Thread ↔ Async Loop)

The recommended architecture uses a command queue:

```
NiceGUI Event Loop (main thread, async)
    │
    │  submit command + Future
    ▼
  [Queue]  ← SAPCommand(method, args, future)
    │
    │  pull command, execute, resolve future
    ▼
SAP COM Worker Thread (dedicated, CoInitialized)
    │
    │  COM calls to SAP GUI
    ▼
  SAP GUI (32/64-bit process)
```

### 6.2 NiceGUI + Background Task Best Practices

From official NiceGUI discussions and documentation:

1. **Never block the main thread**: Any function that takes >100ms should be offloaded via `run.io_bound` or run in a background task.

2. **Use `run.io_bound` for COM calls**: This internally uses `asyncio.loop.run_in_executor()` with a `ThreadPoolExecutor`. You can customize the executor to ensure COM initialization.

3. **Use `background_tasks.create` for fire-and-forget**: When you don't need to await the result inline.

4. **Use `ui.timer` for periodic updates**: Set interval (e.g., 2-5 seconds) for heartbeat checks and UI refresh.

5. **UI updates from background tasks**: When a background task completes and needs to update the UI, it can directly modify NiceGUI elements (if running within the same async context) or use `ui.notify()` for notifications.

6. **Error handling**: Use `app.on_exception()` for global error handling. Wrap all COM calls in try/except for `pywintypes.com_error`.

### 6.3 Configuration Pattern (Pydantic + YAML)

```python
from pydantic import BaseModel, Field
from pathlib import Path
import yaml

class SAPConfig(BaseModel):
    connection_index: int = 0
    session_index: int = 0
    heartbeat_interval: float = 5.0
    command_timeout: float = 120.0

class ExportConfig(BaseModel):
    default_folder: Path = Path("C:/SAP_Exports")
    timestamp_filenames: bool = True
    csv_delimiter: str = ";"

class AppConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    title: str = "SAP GUI Bridge"
    sap: SAPConfig = SAPConfig()
    export: ExportConfig = ExportConfig()

def load_config(path: str = "config.yaml") -> AppConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return AppConfig(**data)
```

---

## 7. Quick Reference: Element ID Patterns

SAP GUI element IDs follow a predictable structure:

| Pattern | Element Type | Example |
|---------|-------------|---------|
| `wnd[0]` | Main window | `session.FindById("wnd[0]")` |
| `wnd[1]` | Modal popup | `session.FindById("wnd[1]")` |
| `wnd[0]/tbar[0]` | System toolbar | OK code field, Enter, Back buttons |
| `wnd[0]/tbar[0]/okcd` | OK code input field | Command/transaction field |
| `wnd[0]/tbar[0]/btn[0]` | Enter button | System toolbar button |
| `wnd[0]/tbar[0]/btn[3]` | Back button | System toolbar button |
| `wnd[0]/tbar[1]` | Application toolbar | Function-key buttons |
| `wnd[0]/tbar[1]/btn[8]` | Execute (F8) | Application toolbar button |
| `wnd[0]/usr` | User area | Main screen content |
| `wnd[0]/usr/txtFIELD` | Text field | Input/display field |
| `wnd[0]/usr/ctxtFIELD` | Context field | Field with F4 search help |
| `wnd[0]/usr/chkFIELD` | Checkbox | |
| `wnd[0]/usr/radFIELD` | Radio button | |
| `wnd[0]/usr/btnFIELD` | Button | |
| `wnd[0]/usr/cmbFIELD` | Combo box | Dropdown |
| `wnd[0]/usr/lblFIELD` | Label | Read-only text |
| `wnd[0]/usr/tblTABLE` | Table control | Classic dynpro table |
| `wnd[0]/usr/cntlCONTROL/shellcont/shell` | ALV Grid | GuiGridView inside a container |
| `wnd[0]/usr/tabsTABSTRIP/tabTABNAME` | Tab | Tab within a tab strip |
| `wnd[0]/mbar` | Menu bar | Top-level menu |
| `wnd[0]/mbar/menu[0]` | First menu | e.g., "System" |
| `wnd[0]/mbar/menu[0]/menu[1]` | Submenu item | |
| `wnd[0]/sbar` | Status bar | Bottom message bar |
| `wnd[0]/sbar/pane[0]` | Status message text | |

**Type prefixes** (from the API):
`txt` = GuiTextField, `ctxt` = GuiCTextField, `lbl` = GuiLabel, `btn` = GuiButton,
`chk` = GuiCheckBox, `rad` = GuiRadioButton, `cmb` = GuiComboBox, `tbl` = GuiTableControl,
`tabs` = GuiTabStrip, `tab` = GuiTab, `sub` = GuiSimpleContainer, `ssub` = GuiScrollContainer,
`shell` = GuiShell (covers GuiGridView, GuiTree, etc.), `titl` = GuiTitlebar

---

## 8. Recommended Learning Path

1. **Start here**: Stefan Schnell's blog post on Python + SAP GUI Scripting (SAP Community link above)
2. **Read**: The SAP GUI Scripting API PDF (at least the introduction, object model overview, and sections on GuiSession, GuiMainWindow, GuiGridView)
3. **Tool up**: Download Scripting Tracker, connect it to a SAP session, explore the element tree
4. **NiceGUI**: Work through the main documentation page, paying special attention to `ui.aggrid`, `ui.tree`, `ui.timer`, and the `run` module
5. **Practice**: Record a simple macro in SAP, convert it to Python, run it from a standalone script
6. **Architect**: Build the COM worker thread prototype, verify it works from an asyncio event loop
7. **Integrate**: Connect the COM worker to a minimal NiceGUI page