# SAP GUI Bridge — Project Plan & Research

## 1. Project Summary

A NiceGUI web application running on the same Windows machine as SAP GUI. It connects to a live SAP session via `win32com` / SAP GUI Scripting COM, and gives the user a browser-based interface to inspect data, run scripts, trigger reports, export files, and monitor the connection — all without touching the SAP GUI window directly.

---

## 2. Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Web UI** | NiceGUI ≥ 3.x | Pure-Python, backend-first, built on FastAPI + Vue/Quasar. Single process, WebSocket-driven live updates. No JS authoring required. |
| **SAP COM bridge** | `win32com.client` (pywin32) | Accesses the `SAPGUI` COM object exposed by SAP GUI for Windows. Standard approach used by all Python-SAP scripting projects. |
| **Async plumbing** | `asyncio` + `run_in_executor` | NiceGUI owns the event loop. All blocking COM calls must be dispatched to a dedicated thread via the executor pattern. |
| **Configuration** | YAML/TOML + Pydantic models | Typed, validated config. Pydantic gives runtime validation; YAML/TOML is human-friendly for paths, connection aliases, report definitions. |
| **Task queue (optional)** | `asyncio.Queue` or lightweight SQLite | For queuing macro/report jobs, tracking status, and allowing the UI to poll progress. |
| **Logging** | `logging` → rotating file + UI log panel | Dual-sink: file for audit, live NiceGUI `ui.log` element for in-browser visibility. |
| **Packaging** | PyInstaller or `nuitka` (optional) | For distributing as a single `.exe` to non-developer users on Windows. |

---

## 3. Prerequisites & Environment

### 3.1 SAP-side requirements

These must be confirmed with the Basis / SAP admin team **before** any development:

1. **Server-side scripting enabled** — profile parameter `sapgui/user_scripting` set to `TRUE` via transaction `RZ11` (or permanently via `RZ10`). Without this, the COM interface is completely blocked.
2. **Recording not disabled** — `sapgui/user_scripting_disable_recording` must be `FALSE` if you want to capture new macros from within the app.
3. **Per-user scripting (optional hardening)** — parameter `sapgui/user_scripting_per_user` can restrict scripting to specific accounts via authorization object `S_SCR`.
4. **Notification pop-ups suppressed** — In SAP GUI Options → Accessibility & Scripting → Scripting, uncheck both notification checkboxes ("Notify when a script attaches…" / "…opens a connection"). Otherwise every COM call triggers a modal dialog.
5. **Low-speed connection OFF** — SAP GUI must not be in low-speed mode; it omits data that the scripting API needs.

### 3.2 Client PC requirements

- Windows 10/11 with SAP GUI for Windows ≥ 7.50 (scripting support installed as a component).
- Python 3.10+ (64-bit recommended, but must match SAP GUI bitness — SAP GUI is typically 32-bit, which may require a 32-bit Python or careful COM marshalling).
- `pywin32` installed (`pip install pywin32`).
- Registry key `HKCU\SOFTWARE\SAP\SAPGUI Front\SAP Frontend Server\Security\UserScripting` = `1`.

### 3.3 Python-SAP bitness alignment

This is a **critical gotcha**: SAP GUI for Windows ships as a 32-bit process. If you use a 64-bit Python, the COM call `win32com.client.GetObject("SAPGUI")` may fail with `"Class not registered"`. Two mitigation strategies:

- **Strategy A (simplest)**: Install and use 32-bit Python.
- **Strategy B**: Use 64-bit Python but register an out-of-process COM proxy. Less tested, not recommended unless 64-bit is mandatory.

Test this **first** before anything else.

---

## 4. Architecture

### 4.1 High-level architecture

```
┌────────────────────────────────────────────────────┐
│                   Windows Machine                  │
│                                                    │
│  ┌──────────┐   COM/OLE    ┌───────────────────┐  │
│  │ SAP GUI  │◄────────────►│  Python Process    │  │
│  │ (32-bit) │  win32com    │                   │  │
│  └──────────┘              │  ┌─────────────┐  │  │
│                            │  │  SAP Bridge  │  │  │
│                            │  │  (COM Thread)│  │  │
│                            │  └──────┬──────┘  │  │
│                            │         │ Queue    │  │
│                            │  ┌──────▼──────┐  │  │
│                            │  │  NiceGUI     │  │  │
│                            │  │  (async loop)│  │  │
│                            │  └──────┬──────┘  │  │
│                            └─────────┼─────────┘  │
│                                      │ WebSocket   │
│                              ┌───────▼───────┐    │
│                              │  Browser Tab  │    │
│                              │  (localhost)   │    │
│                              └───────────────┘    │
└────────────────────────────────────────────────────┘
```

### 4.2 The COM-thread problem (most important architectural decision)

**Core constraint**: COM objects in Windows are apartment-threaded. The `SAPGUI` COM object **must** be created and used from a single thread that has called `pythoncom.CoInitialize()`. NiceGUI's event loop runs on the main thread.

**Solution — Dedicated SAP Worker Thread**:

1. Spawn a single long-lived `threading.Thread` at startup.
2. Inside that thread, call `pythoncom.CoInitialize()` once.
3. The thread owns the COM session object and runs an internal loop that pulls work items from a `queue.Queue`.
4. NiceGUI handlers submit requests to that queue (via `asyncio.get_event_loop().run_in_executor()` or by posting to the queue directly and awaiting an `asyncio.Event`).
5. Results are passed back through `asyncio.Future` objects or a response queue.

This is the **single most critical design decision** in the project. Getting this wrong leads to either COM errors, frozen UI, or race conditions.

### 4.3 Module decomposition

```
sap_gui_bridge/
├── main.py                  # Entry point, starts NiceGUI
├── config.py                # Pydantic settings, YAML loader
├── sap/
│   ├── connection.py        # COM thread lifecycle, connect/disconnect/reconnect
│   ├── session.py           # Session wrapper: FindById, StartTransaction, etc.
│   ├── inspector.py         # Read screen fields, tables (GuiGridView, GuiTableControl)
│   ├── runner.py            # Execute macros / recorded scripts
│   └── exporter.py          # Trigger reports, handle file save dialogs, copy outputs
├── ui/
│   ├── layout.py            # NiceGUI page layout, nav, sidebar
│   ├── pages/
│   │   ├── dashboard.py     # Connection status, session info, quick actions
│   │   ├── inspector.py     # Screen field viewer, table data viewer
│   │   ├── scripts.py       # Script library, run/schedule scripts
│   │   ├── reports.py       # Report definitions, trigger & download
│   │   └── logs.py          # Live log viewer
│   └── components/
│       ├── sap_table.py     # Reusable AG-Grid / table component for SAP data
│       ├── status_bar.py    # Connection heartbeat indicator
│       └── file_picker.py   # Local folder picker for export destinations
├── jobs/
│   ├── queue.py             # Job queue (submit, poll, cancel)
│   └── scheduler.py         # Optional cron-like scheduling for recurring reports
├── utils/
│   ├── threading.py         # COM-safe thread helpers, CoInitialize wrapper
│   └── filesystem.py        # Safe file writes, temp dirs, path sanitization
└── tests/
    ├── test_connection.py
    ├── test_inspector.py
    └── mock_sap.py          # Mock COM objects for testing without SAP
```

---

## 5. Core Feature Breakdown

### 5.1 Connection Management

**What it does**: Attaches to an already-running SAP GUI session, monitors liveness, handles disconnection gracefully.

**Key operations**:
- `GetObject("SAPGUI")` → `GetScriptingEngine` → enumerate `Children` (connections) → enumerate sessions
- Let user pick which connection/session to control (a machine can have multiple SAP logons open)
- Heartbeat: periodically read `session.Info.Transaction` or `session.Info.SystemName` to confirm the session is alive
- On disconnection: notify user, attempt re-attach, queue pending jobs as "paused"

**Gotchas**:
- If SAP GUI is closed entirely, the COM object becomes invalid — `GetObject("SAPGUI")` will throw. Need try/except + retry loop.
- SAP sessions can time out server-side. The COM object will still exist but calls will fail with a COM error.
- Multiple sessions: `application.Children(0)` is the first connection; `connection.Children(0)` is the first session. The user might want to target session index 1 or 2.

### 5.2 Screen Inspector

**What it does**: Reads the current SAP screen and presents field names, values, types, and IDs in a browsable tree or table.

**Key SAP API calls**:
- `session.FindById("wnd[0]")` → main window
- Recursively walk `.Children` to build a tree of all GUI elements
- For each element: `.Type`, `.Name`, `.Id`, `.Text` (if applicable), `.Changeable`
- Special handling for `GuiGridView` (ALV grids): `.RowCount`, `.ColumnCount`, `.GetCellValue(row, col)`
- Special handling for `GuiTableControl`: iterate `.Rows` → `.Cells`

**UI presentation**:
- Tree view of the element hierarchy (NiceGUI `ui.tree`)
- Click a node → show its properties in a detail panel
- "Refresh" button to re-read the screen (SAP screens change as the user navigates)
- For grids/tables: render data in an AG-Grid with sorting, filtering, and CSV export

### 5.3 Script / Macro Execution

**What it does**: Lets the user select a pre-recorded SAP script (VBScript converted to Python calls) and execute it.

**Workflow**:
1. User records a macro using SAP GUI's built-in recorder → saves `.vbs` file
2. A converter utility translates VBScript syntax to Python/win32com calls (mostly: remove `Set`, adjust `.FindById()` calls, replace VB booleans)
3. The converted script is stored in a scripts directory
4. The UI lists available scripts, shows a description, and offers a "Run" button
5. Execution happens on the COM thread; progress/status is pushed to the UI via NiceGUI's live-update mechanism

**Parameters**: Some scripts need runtime parameters (e.g., a material number, date range). Define these in a YAML sidecar file per script, and the UI renders input fields dynamically.

### 5.4 Report Execution & Export

**What it does**: Runs a standard SAP transaction/report (e.g., SE16, MB52, ME2M) with predefined selection parameters, and saves the output to a configured folder.

**Workflow**:
1. Report definitions stored in YAML: transaction code, variant name (if applicable), selection screen field values, output format, destination folder
2. User clicks "Run" → the COM thread navigates to the transaction, fills in selection parameters, executes
3. For ALV output: read grid data via `GetCellValue` loop and write to CSV/Excel
4. For spool/print output: use SAP's "Export" → "Spreadsheet" or "Local File" menu items via scripting
5. File is saved to the configured local folder; UI shows a download link or "open folder" button

**Gotchas**:
- SAP's "Save As" dialog is a native Windows dialog — **not** part of the SAP GUI scripting model. The workaround is to pre-set the default export path in SAP GUI settings, or use clipboard-based extraction (Ctrl+Y to select, Ctrl+C to copy).
- ALV grid scrolling: `GetCellValue` only works for visible rows unless you set the grid's `VisibleRowCount` or use the `firstVisibleRow` property to scroll programmatically and read in chunks.
- Reports with long runtimes: the COM call blocks until SAP returns. Need timeout handling on the worker thread.

### 5.5 Data Export / Download

**What it does**: Extracts currently visible data from any SAP screen and saves it locally.

**Methods**:
- Grid/table extraction → CSV/XLSX (using `openpyxl` or `pandas`)
- Full screen text capture → plain text file
- Clipboard relay: trigger Ctrl+A, Ctrl+C in SAP, read clipboard with `win32clipboard`, parse and save

### 5.6 Connection Monitor & Status Dashboard

**What it does**: Always-visible status bar or dashboard tile showing:
- Connected system (SID, client number, user ID)
- Current transaction code
- Session number
- Heartbeat status (green/yellow/red)
- Pending job count

Uses NiceGUI's `ui.timer` to poll the COM thread's status at ~2-second intervals and update the UI reactively.

---

## 6. Key Technical Challenges & Solutions

### 6.1 COM Threading (reiterated — it's that important)

| Problem | Solution |
|---------|----------|
| COM objects are apartment-threaded | Single dedicated thread with `CoInitialize()` |
| NiceGUI is async, COM is blocking | `run_in_executor()` or explicit queue + Future pattern |
| Can't pass COM objects across threads | The worker thread holds all COM references; other code only passes serializable commands |

### 6.2 Blocking SAP Operations

Some SAP calls (running a report, waiting for a transaction to complete) can block for 30+ seconds.

**Solution**: The COM worker thread is *separate* from the NiceGUI event loop. The UI remains responsive. A progress indicator (spinner or progress bar) shows in the browser. Implement a timeout on the worker side to prevent infinite hangs (e.g., `threading.Event` with timeout).

### 6.3 SAP Modal Dialogs / Pop-ups

SAP frequently shows modal windows (information messages, confirmation dialogs, error pop-ups) that block the scripting API until dismissed.

**Solution**:
- After every major COM call, check `session.ActiveWindow.Type` — if it's `"GuiModalWindow"`, read its text and either auto-dismiss (press Enter) or surface it to the user via a NiceGUI dialog.
- For known pop-ups (e.g., "Data has been saved"), auto-handle based on message text matching.
- Expose an "SAP Dialog" panel in the UI that shows when a modal is detected, with buttons to respond.

### 6.4 Error Handling

COM errors come as `pywintypes.com_error` exceptions with numeric error codes that are not self-explanatory.

**Solution**:
- Wrap all COM calls in a helper that catches `com_error`, logs the raw error, and translates common codes to human-readable messages.
- Common errors: "control not found by ID" (screen changed), "object disconnected" (session lost), "automation error" (generic — usually means SAP is in an unexpected state).
- On "object disconnected": trigger reconnection flow.

### 6.5 SAP GUI Bitness vs. Python Bitness

Already discussed in §3.3. **Test first, decide the Python version early.**

### 6.6 Security Considerations

- **Credentials**: The app attaches to an already-logged-in session. It does **not** handle SAP login credentials. This is by design — the user must log in via SAP GUI first.
- **Network exposure**: NiceGUI serves on `localhost:8080` by default. Do NOT bind to `0.0.0.0` unless you add authentication. By default, anyone on the network could access the UI.
- **Authentication (if needed)**: NiceGUI supports basic auth middleware. For multi-user scenarios (unlikely for a single-machine tool), add a login page.
- **Audit trail**: Log every SAP action (transaction, field changes, exports) with timestamps. SAP's own audit log (SM20) will also capture scripting actions, but a local log gives the user visibility.

---

## 7. NiceGUI-Specific Design Notes

### 7.1 Page structure

Use NiceGUI's multi-page routing:
- `/` → Dashboard (connection status, quick actions)
- `/inspector` → Screen inspector
- `/scripts` → Script library and runner
- `/reports` → Report definitions and execution
- `/logs` → Live log viewer
- `/settings` → Configuration editor (paths, connection preferences)

Use `ui.header`, `ui.left_drawer` for navigation, `ui.footer` for status bar.

### 7.2 Live updates

NiceGUI's WebSocket connection allows pushing updates from server to browser without polling:
- Use `ui.timer(interval, callback)` for periodic status checks
- Use `ui.notify()` for toast-style notifications (job complete, error)
- Use `ui.refreshable` decorator for sections that need to re-render when data changes

### 7.3 Background tasks in NiceGUI

NiceGUI provides several patterns:
- `background_tasks.create(coroutine)` — fire-and-forget async tasks
- `run.io_bound(sync_function, *args)` — wraps `run_in_executor` for blocking I/O
- `run.cpu_bound(sync_function, *args)` — runs in a separate process (not suitable for COM)
- `ui.timer(interval, callback, once=True)` — delayed single-shot tasks

For SAP COM operations, **`run.io_bound`** is the right choice (it uses a thread pool, which we can configure to be our COM-initialized thread).

### 7.4 Data display

For tabular SAP data, the best NiceGUI component is `ui.aggrid` (AG-Grid wrapper):
- Supports large datasets, virtual scrolling, sorting, filtering
- Column definitions can be generated dynamically from SAP grid column metadata
- Built-in CSV export from the grid

---

## 8. Configuration Schema

```yaml
# config.yaml
app:
  host: "127.0.0.1"        # Do NOT use 0.0.0.0 without auth
  port: 8080
  title: "SAP GUI Bridge"
  dark_mode: true

sap:
  connection_index: 0       # Which SAP connection to attach to
  session_index: 0          # Which session within that connection
  heartbeat_interval: 5     # Seconds between liveness checks
  auto_reconnect: true
  command_timeout: 120      # Max seconds for a single SAP operation

export:
  default_folder: "C:\\SAP_Exports"
  csv_delimiter: ";"
  excel_engine: "openpyxl"
  timestamp_filenames: true

scripts:
  directory: "./scripts"
  auto_discover: true

reports:
  definitions_file: "./reports.yaml"

logging:
  level: "INFO"
  file: "./logs/bridge.log"
  max_bytes: 10485760       # 10 MB
  backup_count: 5
```

---

## 9. Development Phases

### Phase 1 — Foundation (Week 1–2)

**Goal**: Prove that the COM bridge works and NiceGUI can drive it.

- [ ] Validate Python bitness vs. SAP GUI bitness (test `GetObject("SAPGUI")`)
- [ ] Build the COM worker thread with `CoInitialize`, queue, and Future-based response
- [ ] Create minimal NiceGUI app with a single page that shows connection status
- [ ] Implement connect / disconnect / heartbeat
- [ ] Display basic session info (system name, client, user, current transaction)

**Deliverable**: A running app that attaches to SAP and shows "Connected to [SID]" in the browser.

### Phase 2 — Screen Inspector (Week 3–4)

**Goal**: Read and display SAP screen contents.

- [ ] Recursive element tree walker for `session.FindById("wnd[0]")`
- [ ] NiceGUI tree component rendering the element hierarchy
- [ ] Detail panel for selected element (type, ID, value, changeable flag)
- [ ] Grid/table data extractor for `GuiGridView` and `GuiTableControl`
- [ ] AG-Grid display of extracted table data
- [ ] "Export to CSV" button for table data

**Deliverable**: User can browse any SAP screen's structure and export table data.

### Phase 3 — Script Runner (Week 5–6)

**Goal**: Execute pre-built SAP scripts from the UI.

- [ ] VBScript → Python converter utility (regex-based, covers 80% of recorded scripts)
- [ ] Script discovery from configured directory
- [ ] Script metadata / parameter definition (YAML sidecar)
- [ ] Dynamic parameter input form in the UI
- [ ] Execution on COM thread with progress indicator
- [ ] Result / error display in the UI
- [ ] Execution history log

**Deliverable**: User can select a script, fill in parameters, click Run, and see results.

### Phase 4 — Report Engine (Week 7–8)

**Goal**: Define, trigger, and export standard SAP reports.

- [ ] Report definition schema (YAML) with transaction, variant, selection fields, output config
- [ ] Report list page in the UI
- [ ] Execution engine: navigate to transaction, fill selection screen, execute
- [ ] Output capture: ALV grid reading, clipboard extraction, or file export
- [ ] Save output to configured folder with timestamped filename
- [ ] Download link in the UI
- [ ] Error handling for SAP pop-ups during report execution

**Deliverable**: User can trigger predefined reports and download results.

### Phase 5 — Polish & Hardening (Week 9–10)

**Goal**: Production-ready robustness.

- [ ] Comprehensive error handling with user-friendly messages
- [ ] Reconnection logic (auto-retry on session loss)
- [ ] Settings page for editing config without touching YAML
- [ ] Log viewer page with filtering and search
- [ ] Job queue for long-running operations (with cancel support)
- [ ] Documentation (user guide, script authoring guide)
- [ ] Optional: PyInstaller packaging for single-file distribution
- [ ] Optional: Basic auth middleware for network-exposed deployments

---

## 10. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| SAP admin refuses to enable scripting | **Blocker** — project cannot proceed | Medium | Engage Basis team early. Provide SAP's own security guide. Offer to restrict to specific users via `S_SCR` auth object. |
| 32-bit/64-bit mismatch | Blocks COM connection | High (if not tested early) | Test in Phase 1, Day 1. Keep 32-bit Python as fallback. |
| SAP modal dialogs interrupt automation | Scripts hang waiting for user input | High | Build a modal-dialog detection and auto-dismiss layer. Surface unexpected dialogs to the browser UI. |
| NiceGUI event loop blocked by COM calls | UI freezes | High (if architecture is wrong) | Strict separation: COM thread ≠ async loop. Never call COM from the main thread. |
| SAP screen layout changes between versions | Element IDs break | Medium | Use robust selectors (match by type + name, not just absolute ID). Build a "verify element exists" helper. |
| Large ALV grids (10k+ rows) | Slow extraction via `GetCellValue` loop | Medium | Use clipboard-based extraction (Ctrl+A, Ctrl+C) for large datasets. Show progress bar. Consider chunked reading. |
| SAP session timeout during long operations | COM object becomes invalid mid-operation | Medium | Wrap all operations in timeout + try/except. Re-check session liveness before and after. |

---

## 11. Dependencies (pip packages)

```
nicegui>=3.0
pywin32
pydantic>=2.0
pyyaml
openpyxl          # Excel export
pandas            # Optional, for data manipulation
loguru            # Optional, nicer logging API
```

---

## 12. Testing Strategy

| Layer | Approach |
|-------|----------|
| COM bridge | Manual integration tests on a Windows machine with SAP GUI running. Cannot be meaningfully unit-tested without SAP. |
| Mock COM layer | Build a `MockSAPSession` class that simulates `FindById`, `GetCellValue`, etc. Use this for all UI and logic tests. |
| NiceGUI UI | NiceGUI has a built-in testing framework (`nicegui.testing`). Use it for page rendering tests. |
| VBScript converter | Pure-function unit tests with input VBS snippets and expected Python output. |
| Config loading | Pydantic model validation tests with valid and invalid YAML. |
| End-to-end | Manual smoke tests on a real SAP system for each phase deliverable. |

---

## 13. Open Questions to Resolve

1. **Which SAP systems/clients will this target?** (Production, QA, Dev — affects risk tolerance for scripting enablement)
2. **Single user or multi-user?** (If only the local user accesses `localhost`, auth is optional. If exposed on the network, auth is mandatory.)
3. **Which specific transactions and reports are in scope?** (Drives the report definition work in Phase 4)
4. **Is there an existing library of recorded VBScript macros?** (Reduces Phase 3 effort)
5. **Are there corporate policies around installing Python / running custom executables?** (Affects deployment strategy)
6. **What SAP GUI version is installed?** (Scripting API varies slightly across 7.50, 7.60, 7.70, 8.00)
7. **Is PyRFC (direct RFC calls) a viable complement?** (For some data extraction tasks, direct RFC is more reliable than GUI scraping — but requires the SAP NetWeaver RFC SDK and different SAP-side permissions)

---

## 14. Next Steps (Immediate Actions)

1. **Confirm SAP scripting is enabled** — talk to the Basis admin, get `sapgui/user_scripting = TRUE` on at least the dev/QA system.
2. **Test the COM connection** — on the target machine, open SAP GUI, log in, then run a 5-line Python script to verify `GetObject("SAPGUI")` works. This is the single most important validation.
3. **Decide Python bitness** — based on the COM connection test above.
4. **Set up the project skeleton** — virtual environment, folder structure, `config.yaml`, basic NiceGUI app that shows "Hello World".
5. **Build the COM worker thread prototype** — the hardest architectural piece. Get this right before building any UI.
6. **Identify the first 3 use cases** — pick the most valuable scripts/reports to target, so Phase 3–4 development is focused on real needs.