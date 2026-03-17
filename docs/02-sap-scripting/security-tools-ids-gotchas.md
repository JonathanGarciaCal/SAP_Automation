# SAP GUI Scripting — Security, Tools & Element ID Patterns

## Security Parameters (for SAP Basis Admin)

### Server-Side (Transaction RZ11 or RZ10)

| Parameter | Value | Effect |
|-----------|-------|--------|
| `sapgui/user_scripting` | `TRUE` | **Required** — enables the scripting API entirely |
| `sapgui/user_scripting_per_user` | `TRUE` | Restrict scripting to users with auth object `S_SCR` |
| `sapgui/user_scripting_disable_recording` | `FALSE` | Must be FALSE to allow macro recording |
| `sapgui/user_scripting_set_readonly` | `FALSE` | If TRUE, scripts can only read — no data changes |
| `sapgui/user_scripting_force_notification` | `FALSE` | If FALSE, suppresses the server-side notification pop-up |

- `RZ11`: Changes take effect immediately but are lost on server restart.
- `RZ10`: Changes are permanent but require a restart to take effect.

### Client-Side (SAP GUI Options)

Path: SAP GUI → Options → Accessibility & Scripting → Scripting

- [x] **Enable scripting** — must be checked
- [ ] **Notify when a script attaches to SAP GUI** — uncheck for automation
- [ ] **Notify when a script opens a connection** — uncheck for automation

### Windows Registry (alternative to GUI options)

```
HKCU\SOFTWARE\SAP\SAPGUI Front\SAP Frontend Server\Security
    UserScripting = 1        (enable scripting)
```

### Authorization Object `S_SCR` (for per-user control)

When `sapgui/user_scripting_per_user = TRUE`, each user needs the authorization object `S_SCR` assigned via their role. Without it, scripting is blocked for that user even if enabled server-side.

---

## Development Tools

### SAP Built-in Script Recorder

- **Access**: SAP GUI menu bar → Customize Local Layout (icon) → Script Recording and Playback
- **Output**: `.vbs` files in VBScript
- **Good for**: Quick recording of simple transactions
- **Limitations**: Cannot inspect element properties. Doesn't capture GuiTree node clicks or GuiGridView cell values reliably. Recording quality varies.

### Scripting Tracker (Stefan Schnell)

- **Download**: `https://tracker.stschnell.de/` — No installation needed, just extract and run `Tracker.exe`
- **Status**: Retired/unmaintained, but still works with SAP GUI 7.x and 8.x
- **Current version**: 6.x (32-bit and 64-bit versions available)

**Features**:
- **Analyzer tab**: Shows a tree of all SAP sessions and their scripting objects. Click any node to see its ID, type, properties. Right-click → highlights the element with a red border in SAP.
- **Recorder tab**: Records actions in VBScript, PowerShell, Python, or AutoIt syntax. Better than SAP's built-in recorder.
- **Scripting API tab**: Built-in reference of all objects, methods, and properties.
- **Comparator tab**: Compare two screens to find element differences.

### Object Browser via sapfewse.ocx

The SAP GUI Scripting type library is in: `C:\Program Files\SAP\FrontEnd\SAPgui\sapfewse.ocx`

You can load this in Excel's VBA Object Browser (Tools → References → Browse → select sapfewse.ocx) to see all classes, methods, and properties with IntelliSense.

---

## Element ID Patterns

SAP GUI element IDs follow a hierarchical path structure:

### ID Path Structure
```
/app/con[0]/ses[0]/wnd[0]/usr/ctxtFIELD-NAME
  │     │      │     │     │    │
  │     │      │     │     │    └─ Type prefix + field name
  │     │      │     │     └─ User area
  │     │      │     └─ Window index
  │     │      └─ Session index
  │     └─ Connection index
  └─ Application root
```

When using `session.FindById()`, the path is relative to the session:
```
wnd[0]/usr/ctxtFIELD-NAME    ← Relative (used with session.FindById)
```

### Common Patterns

| Pattern | Element | Example |
|---------|---------|---------|
| `wnd[0]` | Main window | `session.FindById("wnd[0]")` |
| `wnd[1]` | First modal popup | `session.FindById("wnd[1]")` |
| `wnd[0]/tbar[0]/okcd` | OK code / command field | Transaction input field |
| `wnd[0]/tbar[0]/btn[N]` | System toolbar button | `btn[0]`=Enter, `btn[3]`=Back |
| `wnd[0]/tbar[1]/btn[N]` | Application toolbar button | `btn[8]`=Execute (F8) |
| `wnd[0]/usr` | User area (main content) | Container for all screen fields |
| `wnd[0]/usr/txtFIELD` | Text field | Simple input/display |
| `wnd[0]/usr/ctxtFIELD` | Context field (with F4) | Input with search help |
| `wnd[0]/usr/chkFIELD` | Checkbox | |
| `wnd[0]/usr/radFIELD` | Radio button | |
| `wnd[0]/usr/btnFIELD` | Button | |
| `wnd[0]/usr/cmbFIELD` | Combo box | Dropdown |
| `wnd[0]/usr/lblFIELD` | Label | Read-only text |
| `wnd[0]/usr/tblTABLE` | Table control | Classic dynpro table |
| `wnd[0]/usr/cntlCTRL/shellcont/shell` | ALV Grid | GuiGridView inside custom control |
| `wnd[0]/usr/tabsTABSTRIP/tabTAB` | Tab within tabstrip | |
| `wnd[0]/usr/subSUBSCREEN:PROG:DYNNR` | Subscreen | |
| `wnd[0]/mbar/menu[N]` | Menu bar item | |
| `wnd[0]/mbar/menu[N]/menu[M]` | Submenu | |
| `wnd[0]/sbar` | Status bar | Message display area |
| `wnd[0]/sbar/pane[0]` | Status message text | |

### Finding IDs

1. **Scripting Tracker**: Best tool — visual tree browser
2. **Record a macro**: The `.vbs` file contains all the IDs used
3. **SAP Technical Information**: Place cursor on field → F1 → Technical Information → Screen Field shows the field name
4. **Programmatic tree walk**: Use the recursive walker pattern from the object-model doc

---

## Known Gotchas & Workarounds

### 1. "The control could not be found by id" (Error 619)
- **Cause**: Screen changed, element doesn't exist on current screen, or ID path is wrong
- **Fix**: Verify the screen/transaction before accessing elements. Use `try/except`. Build a `safe_find` wrapper.
- **Pattern**:
  ```python
  def safe_find(session, element_id):
      try:
          return session.FindById(element_id)
      except Exception:
          return None
  ```

### 2. COM object disconnected
- **Cause**: SAP GUI was closed, session timed out, or user logged off
- **Fix**: Catch `pywintypes.com_error`, detect the disconnection, trigger reconnection flow.

### 3. Script hangs indefinitely
- **Cause**: A modal dialog appeared that the script didn't expect
- **Fix**: Always check `session.ActiveWindow.Type` after actions that might trigger pop-ups.

### 4. ALV grid data reads are slow for large datasets
- **Cause**: `GetCellValue` makes a COM call per cell
- **Fix**: Use clipboard extraction (Ctrl+A → Ctrl+C → read clipboard) for 1000+ rows.

### 5. F4 help dialogs don't work with scripting
- **Cause**: SAP's F4 help can run in "Control" mode which doesn't expose scripting objects
- **Fix**: Change to "Dialog" mode: SAP GUI → Options → Expert → uncheck "Use controls for F4 help"

### 6. Python 64-bit can't access 32-bit SAP GUI COM
- **Cause**: COM bitness mismatch
- **Fix**: Use Python matching SAP GUI bitness. Or upgrade SAP GUI to 8.00 64-bit.

### 7. Scripts work in VBScript but fail in Python
- **Cause**: Usually missing parentheses on method calls, or VBS-specific syntax
- **Fix**: Follow the conversion rules in vbs-to-python.md

### 8. Recording doesn't capture all actions
- **Cause**: Some controls (GuiTree nodes, GuiGridView cell clicks) don't record well
- **Fix**: Use Scripting Tracker to identify the element, then write the interaction code manually.

### 9. SAP session becomes "Busy" indefinitely
- **Cause**: Server-side processing is slow, or a background job is running
- **Fix**: Check `session.Busy` property. Implement a timeout. Consider using `session.FindById("wnd[0]").SendVKey(12)` to cancel.

### 10. Multiple users on same server clash
- **Cause**: One user's script changes data that another user is viewing
- **Fix**: Not a scripting problem — same as manual SAP usage. Use proper SAP locking and authorization.
