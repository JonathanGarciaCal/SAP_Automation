# Risk Matrix & Mitigations

## Critical Risks (Project Blockers)

### SAP Admin Refuses to Enable Scripting
- **Impact**: Project cannot proceed at all
- **Likelihood**: Medium
- **Mitigation**: Engage Basis team early. Provide SAP's own Security Guide showing it's an official feature. Offer per-user restriction via `S_SCR` authorization object. Start with dev/QA system only. Emphasize that scripting has the same access rights as the logged-in user — it can't do anything the user can't already do manually.

### 32-bit/64-bit Mismatch
- **Impact**: COM connection fails entirely
- **Likelihood**: High (if not tested on Day 1)
- **Mitigation**: Test the 5-line COM script before writing any application code. Keep 32-bit Python as fallback. SAP GUI 8.00+ offers 64-bit, which eliminates this issue.

## High Risks (Architecture Failures)

### NiceGUI Event Loop Blocked by COM Calls
- **Impact**: UI freezes, WebSocket disconnects, users think app is broken
- **Likelihood**: High (if architecture is wrong)
- **Mitigation**: Strict separation — COM calls happen ONLY on the dedicated worker thread. Never call COM from the main thread. The producer-consumer queue pattern enforces this boundary.

### SAP Modal Dialogs Interrupt Automation
- **Impact**: Scripts hang indefinitely waiting for user to dismiss a pop-up
- **Likelihood**: High
- **Mitigation**: After every major COM call, check `session.ActiveWindow.Type`. If it's `"GuiModalWindow"`, read its text and either auto-dismiss (for known messages) or relay to the browser UI via `ui.dialog`. Build a configurable auto-dismiss list for common pop-ups.

## Medium Risks

### SAP Screen Layout Changes Between Versions
- **Impact**: Element IDs break, scripts fail
- **Likelihood**: Medium
- **Mitigation**: Use robust selectors where possible (match by type + name, not just absolute ID path). Build a "verify element exists" helper that wraps `FindById` with try/except. Document which SAP version scripts were recorded on.

### Large ALV Grids (10k+ Rows)
- **Impact**: Slow extraction via `GetCellValue` loop (minutes for large datasets)
- **Likelihood**: Medium
- **Mitigation**: Use clipboard-based extraction (Ctrl+A, Ctrl+C) for large datasets — this is orders of magnitude faster. Show a progress bar during extraction. For very large data needs, consider PyRFC with `RFC_READ_TABLE` which bypasses the GUI entirely.

### SAP Session Timeout During Long Operations
- **Impact**: COM object becomes invalid mid-operation, causing cryptic errors
- **Likelihood**: Medium
- **Mitigation**: Wrap all operations in timeout + try/except for `pywintypes.com_error`. Re-check session liveness before and after long operations. Implement auto-reconnect: detect "object disconnected" errors and re-attach to the session.

## Low Risks

### NiceGUI Breaking Changes
- **Impact**: UI code needs updates on framework upgrade
- **Likelihood**: Low (NiceGUI 3.x is stable)
- **Mitigation**: Pin NiceGUI version in requirements.txt. Test upgrades in a branch.

### Corporate Policy Blocks Python Installation
- **Impact**: Can't run the tool on target machines
- **Likelihood**: Low-Medium (depends on IT policy)
- **Mitigation**: PyInstaller can package everything into a single `.exe` that doesn't require a Python installation. Alternatively, use a portable Python distribution.

### Multiple SAP Sessions Cause Confusion
- **Impact**: Bridge connects to wrong session, or actions affect wrong window
- **Likelihood**: Low
- **Mitigation**: At startup, enumerate all connections and sessions, show them in a dropdown, and let the user explicitly choose which session to control. Display the session's SID + client + user prominently.
