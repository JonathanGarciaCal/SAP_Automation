# Development Phases

## Phase 1 — Foundation (Week 1–2)

**Goal**: Prove that the COM bridge works and NiceGUI can drive it.

- [ ] Validate Python bitness vs SAP GUI bitness (test `GetObject("SAPGUI")`)
- [ ] Build the COM worker thread with `CoInitialize`, queue, and Future-based response
- [ ] Create minimal NiceGUI app with a single page showing connection status
- [ ] Implement connect / disconnect / heartbeat
- [ ] Display basic session info (system name, client, user, current transaction)

**Deliverable**: A running app that attaches to SAP and shows "Connected to [SID]" in the browser.

**Success criteria**: The browser shows live session info that updates when you switch transactions in SAP GUI.

---

## Phase 2 — Screen Inspector (Week 3–4)

**Goal**: Read and display SAP screen contents.

- [ ] Recursive element tree walker for `session.FindById("wnd[0]")`
- [ ] NiceGUI tree component rendering the element hierarchy
- [ ] Detail panel for selected element (type, ID, value, changeable flag)
- [ ] Grid/table data extractor for `GuiGridView` and `GuiTableControl`
- [ ] AG-Grid display of extracted table data
- [ ] "Export to CSV" button for table data

**Deliverable**: User can browse any SAP screen's structure and export table data.

**Success criteria**: Open SE16 in SAP, display a table, and the inspector shows all grid data in the browser with working CSV export.

---

## Phase 3 — Script Runner (Week 5–6)

**Goal**: Execute pre-built SAP scripts from the UI.

- [ ] VBScript → Python converter utility (regex-based, covers 80% of recorded scripts)
- [ ] Script discovery from configured directory
- [ ] Script metadata / parameter definition (YAML sidecar)
- [ ] Dynamic parameter input form in the UI
- [ ] Execution on COM thread with progress indicator
- [ ] Result / error display in the UI
- [ ] Execution history log

**Deliverable**: User can select a script, fill in parameters, click Run, and see results.

**Success criteria**: A converted VBScript macro runs successfully from the browser UI with user-provided parameters.

---

## Phase 4 — Report Engine (Week 7–8)

**Goal**: Define, trigger, and export standard SAP reports.

- [ ] Report definition schema (YAML) with transaction, variant, selection fields, output config
- [ ] Report list page in the UI
- [ ] Execution engine: navigate to transaction, fill selection screen, execute
- [ ] Output capture: ALV grid reading, clipboard extraction, or file export
- [ ] Save output to configured folder with timestamped filename
- [ ] Download link in the UI
- [ ] Error handling for SAP pop-ups during report execution

**Deliverable**: User can trigger predefined reports and download results.

**Success criteria**: A report like MB52 (warehouse stocks) runs with predefined parameters and produces an Excel file.

---

## Phase 5 — Polish & Hardening (Week 9–10)

**Goal**: Production-ready robustness.

- [ ] Comprehensive error handling with user-friendly messages
- [ ] Reconnection logic (auto-retry on session loss)
- [ ] Settings page for editing config without touching YAML
- [ ] Log viewer page with filtering and search
- [ ] Job queue for long-running operations (with cancel support)
- [ ] SAP modal dialog detection and auto-handling / relay to browser
- [ ] Documentation (user guide, script authoring guide)
- [ ] Optional: PyInstaller packaging for single-file distribution
- [ ] Optional: Basic auth middleware for network-exposed deployments

---

## Phase 0 — Pre-Development Validation (Before Anything Else)

These must be done before Phase 1 starts:

1. **Talk to SAP Basis admin** — Get scripting enabled on dev/QA system
2. **Run the 5-line COM test** on the target machine:
   ```python
   import win32com.client
   SapGui = win32com.client.GetObject("SAPGUI")
   engine = SapGui.GetScriptingEngine
   session = engine.FindById("ses[0]")
   print(f"Connected: {session.Info.SystemName} / {session.Info.User}")
   ```
3. **Confirm Python bitness** — If the test fails, try the other bitness
4. **Identify first 3 target use cases** — Which scripts/reports will be automated first
