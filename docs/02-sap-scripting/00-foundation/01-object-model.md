# SAP GUI Object Model & Architecture

Understanding the SAP GUI object model is the foundation for effective scripting. This page explains how SAP GUI structures its objects and how to navigate the hierarchy.

## Table of Contents

1. [Runtime Hierarchy](#hierarchy)
2. [Key Objects Reference](#objects)
3. [Finding Element IDs](#finding)
4. [Window Structure](#windows)
5. [Common Controls](#controls)
6. [Accessing Objects](#accessing)

---

## Runtime Hierarchy {#hierarchy}

SAP GUI Scripting represents the entire SAP environment as a tree of COM objects:

```
SAPGUI (Root COM Object)
  │
  └─ Application (GetScriptingEngine)
      │
      └─ Connection[0] (First SAP system, e.g., PRD)
      │  │
      │  ├─ Session[0] (SESSION_MANAGER — main menu)
      │  │  ├─ Window (wnd[0] — main window)
      │  │  │  ├─ Titlebar
      │  │  │  ├─ Toolbars (tbar[0], tbar[1], ...)
      │  │  │  │  ├─ OK Code field (okcd) ← type transaction codes here
      │  │  │  │  ├─ Buttons (btn[0], btn[1], ...)
      │  │  │  │  └─ ...
      │  │  │  ├─ UserArea (usr) ← main content
      │  │  │  │  ├─ Text fields (txt..., ctxt...)
      │  │  │  │  ├─ Checkboxes (chk...)
      │  │  │  │  ├─ Radio buttons (rad...)
      │  │  │  │  ├─ Tables (tbl...)
      │  │  │  │  ├─ Grids (GuiGridView via cntl.../shellcont/shell)
      │  │  │  │  ├─ Trees
      │  │  │  │  ├─ Dropdowns (cmb...)
      │  │  │  │  └─ ... (all UI elements)
      │  │  │  ├─ Menubar
      │  │  │  └─ Statusbar
      │  │  │
      │  │  └─ Windows (wnd[1], wnd[2], ...) ← dialog boxes
      │  │
      │  ├─ Session[1] (Another transaction, e.g., MM01)
      │  │  └─ Window & Contents (same as Session[0])
      │  │
      │  └─ Session[2..N] (More sessions)
      │
      └─ Connection[1] (Second SAP system, e.g., DEV)
         └─ Sessions...

```

### Key Takeaways

- **One Application per SAP GUI process** — All your connections and sessions go through one root
- **Multiple Connections** — You can have PRD, DEV, and QAS connections simultaneously
- **Multiple Sessions per Connection** — Each session is like an open window to a transaction
- **Session[0] is always SESSION_MANAGER** — The main menu; other sessions are open transactions
- **Windows within Sessions** — wnd[0] is main, wnd[1]+ are dialogs (sort by appearance order)

---

## Key Objects Reference {#objects}

### GuiApplication (Root Scripting Engine)

Accessed via: `sap_gui.GetScriptingEngine`

| Property/Method | Type | Returns | Purpose |
|---|---|---|---|
| `Children.Count` | Property | Integer | Number of open connections |
| `Children(index)` | Accessor | GuiConnection | Get connection by index (0-based) |
| `ActiveConnection` | Property | GuiConnection | Currently focused connection |
| `ActiveSession` | Property | GuiSession | Currently focused session globally |

```python
app = sap_gui.GetScriptingEngine
print(f"Open connections: {app.Children.Count}")

# Get first connection
connection = app.Children(0)

# Get currently active connection
active_conn = app.ActiveConnection
```

---

### GuiConnection (SAP System Connection)

| Property/Method | Type | Returns | Purpose |
|---|---|---|---|
| `Children.Count` | Property | Integer | Number of sessions in this connection |
| `Children(index)` | Accessor | GuiSession | Get session by index |
| `Info.SystemName` | Property | String | System ID (e.g., "PRD", "DEV", "QAS") |
| `Info.Client` | Property | String | Client number (e.g., "100") |
| `Info.User` | Property | String | Logged-in user |
| `Info.Language` | Property | String | Login language (e.g., "EN", "DE") |
| `Info.ApplicationServer` | Property | String | Server hostname |

```python
connection = app.Children(0)

print(f"System: {connection.Children(0).Info.SystemName}")  # PRD
print(f"Client: {connection.Children(0).Info.Client}")  # 100
print(f"Sessions open: {connection.Children.Count}")
```

---

### GuiSession (Single Transaction Window)

| Property/Method | Type | Returns | Purpose |
|---|---|---|---|
| `Info.SystemName` | Property | String | SAP system ID |
| `Info.Client` | Property | String | Client number |
| `Info.User` | Property | String | Logged-in user |
| `Info.Transaction` | Property | String | Current transaction code (e.g., "MM01", "SESSION_MANAGER") |
| `Info.Dynpro` | Property | String | Screen number (e.g., "1000") |
| `Info.Program` | Property | String | ABAP program name |
| `ActiveWindow` | Property | GuiWindow | Currently active window (main or modal) |
| `Children(index)` | Accessor | GuiWindow | Get window by index (0=main, 1+=dialogs) |
| `FindById(id)` | Method | GuiComponent | Find element by full path ID |
| `FindByName(name, type)` | Method | GuiComponent | Find first element with name & type |
| `StartTransaction(code)` | Method | void | Navigate to transaction |
| `SendCommand(code)` | Method | void | Execute OK code (e.g., "/nMM01") |
| `CreateSession()` | Method | GuiSession | Open new session window |
| `EndTransaction()` | Method | void | End current transaction (/n) |

```python
session = connection.Children(0)

# Read session info
print(f"Transaction: {session.Info.Transaction}")  # SESSION_MANAGER
print(f"User: {session.Info.User}")  # TESTUSER

# Navigate to transaction
session.StartTransaction("MM01")  # Go to Material Master

# Or use SendCommand
session.SendCommand("/nMM01")

# Create new session window (opens Session[N])
new_session = session.CreateSession()

# Access element in main window
main_window = session.ActiveWindow  # or session.Children(0)
```

---

### GuiMainWindow (wnd[0] — Primary Window)

| Property | Type | Purpose |
|---|---|---|
| `Id` | String | Always "wnd[0]" |
| `Text` | String | Window title |
| `Handle` | Long | Win32 window handle (for advanced integration) |
| `Busy` | Boolean | True while SAP processes a server request |

| Method | Purpose |
|---|---|
| `SendVKey(key)` | Press keyboard combinations (see [Virtual Keys](../01-quick-reference/virtual-keys.md)) |
| `SendKeyboardInput(text)` | Type text character-by-character |
| `SetFocus()` | Bring window to foreground |
| `Maximize()` | Maximize window |
| `Iconify()` | Minimize to taskbar |
| `Close()` | Close window |

```python
main_window = session.FindById("wnd[0]")

# Press Enter
main_window.SendVKey(0)

# Press F8 (Execute)
main_window.SendVKey(96)

# Maximize the window
main_window.Maximize()

# Wait for SAP to finish processing
while main_window.Busy:
    time.sleep(0.1)
```

---

### GuiUserArea (usr — Main Content Area)

The `UserArea` (wnd[0]/usr) contains all UI elements: text fields, buttons, dropdowns, tables, grids.

**Not directly accessed; instead, access child elements:**

```python
# Text field in user area
field = session.FindById("wnd[0]/usr/ctxtMATNR")

# Text label
label = session.FindById("wnd[0]/usr/lblLABEL_NAME")

# Button
button = session.FindById("wnd[0]/usr/btnBUTTON_NAME")

# Grid (ALV)
grid = session.FindById("wnd[0]/usr/cntlCTRL_NAME/shellcont/shell")

# Table
table = session.FindById("wnd[0]/usr/tblTABLE_NAME")
```

---

### GuiModalWindow (wnd[1], wnd[2], ... — Dialogs)

Dialog boxes (popups) are indexed after the main window.

```python
# Main window
main_window = session.FindById("wnd[0]")

# First dialog (appears on top)
dialog = session.FindById("wnd[1]")

# Second dialog (if nested)
nested_dialog = session.FindById("wnd[2]")

# Navigate within dialogs — check current active window
current = session.ActiveWindow

if current.Id == "wnd[1]":
    print("Dialog is active")
else:
    print("Main window is active")
```

---

## Finding Element IDs {#finding}

### Method 1: Use Scripting Tracker (Recommended)

**Download:** [Scripting Tracker by Stefan Schnell](https://www.stschnell.de/)

**How to use:**
1. Open Scripting Tracker application
2. Click "**Refresh**" button (in toolbar)
3. Click on SAP GUI elements → they highlight in Scripting Tracker
4. Right-click element → "**Copy ID**"
5. Paste into your script

**Example:**
```
Scripting Tracker shows:
  Name: MATNR
  Type: GuiCTextField
  ID: /app/con[0]/ses[0]/wnd[0]/usr/ctxtMATNR
  
Shortened ID (relative): wnd[0]/usr/ctxtMATNR
```

### Method 2: Element ID Format

All element IDs follow a hierarchical path:

```
wnd[0]                              — Main window
wnd[0]/tbar[0]                      — Toolbar 0
wnd[0]/tbar[0]/okcd                 — OK code field
wnd[0]/usr/ctxtMATNR                — Text field "MATNR"
wnd[0]/usr/cntlCTRL/shellcont/shell — Grid control
wnd[1]                              — Dialog box
```

**Element type prefixes:**
| Prefix | Control Type |
|--------|---|
| `txt` | Text field (read-only) |
| `ctxt` | Text field with F4 search |
| `pwd` | Password field |
| `chk` | Checkbox |
| `rad` | Radio button |
| `btn` | Button |
| `cmb` | Dropdown (combo box) |
| `lbl` | Label (read-only text) |
| `tbl` | Table control |
| `tbar` | Toolbar |
| `okcd` | OK code field (transaction input) |
| `cntl` | Custom control container (→ subpath), used for grids/trees/editors |
| `sbar` | Status bar |

### Method 3: FindByName (Slower, but Useful)

```python
# Find element by name (not recommended; use ID instead)
field = session.FindByName("MATNR", "GuiCTextField")

# Returns first matching element
# Less reliable than FindById because names can duplicate
```

### Method 4: Search for Elements Programmatically

```python
def find_all_text_fields_in_user_area(session):
    """Find all text fields in main window"""
    window = session.FindById("wnd[0]")
    user_area = session.FindById("wnd[0]/usr")
    
    text_fields = []
    
    # This requires recursive traversal (not built into GuiComponent)
    # Usually easier to use Scripting Tracker instead
    
    return text_fields

# More practical: check if element exists
def element_exists(session, element_id):
    """Check if element can be found"""
    try:
        session.FindById(element_id)
        return True
    except:
        return False

# Usage
if element_exists(session, "wnd[0]/usr/ctxtMATNR"):
    print("Material field exists")
else:
    print("Material field not found (maybe wrong transaction)")
```

---

## Window Structure {#windows}

### Multiple Windows in a Session

Windows are indexed by order of appearance. Typically:

```
wnd[0]  — Main window (always open for the session)
wnd[1]  — First dialog box (if one appears)
wnd[2]  — Second dialog (if nested), or previous dialog if first one closed
...
```

### Working with Windows

```python
session = connection.Children(0)

# Get main window
main_window = session.Children(0)

# Get a dialog (if open)
dialog = session.FindById("wnd[1]")  # May throw if not open

# Get currently active window
active_window = session.ActiveWindow

# Check which window is active
if session.ActiveWindow.Id == "wnd[0]":
    print("Main window active")
else:
    print(f"Dialog active: {session.ActiveWindow.Id}")

# Wait for dialog to close
while dialog exists:
    pass  # Dialog is still open

# Safer approach:
def wait_for_dialog_close(session, timeout=5):
    """Wait for any dialog (wnd[1]...) to close"""
    import time
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            session.FindById("wnd[1]")
            time.sleep(0.1)
        except:
            print("Dialog closed")
            return True
    
    print("Dialog did not close in time")
    return False
```

---

## Common Controls {#controls}

### Text Fields

```python
# Read text
value = session.FindById("wnd[0]/usr/ctxtFIELD").text

# Write text
session.FindById("wnd[0]/usr/ctxtFIELD").text = "new value"

# Check if field is changeable
is_editable = session.FindById("wnd[0]/usr/ctxtFIELD").changeable

# Tab key to next field
session.FindById("wnd[0]/usr/ctxtFIELD").SetFocus()
session.FindById("wnd[0]").SendVKey(9)  # Tab
```

### Buttons

```python
# Click a button
session.FindById("wnd[0]/usr/btnBUTTON").press()

# Buttons in toolbar
session.FindById("wnd[0]/tbar[0]/btn[0]").press()  # Enter
session.FindById("wnd[0]/tbar[0]/btn[3]").press()  # Back
```

### Checkboxes

```python
# Check a checkbox
session.FindById("wnd[0]/usr/chkFLAG").selected = True

# Uncheck
session.FindById("wnd[0]/usr/chkFLAG").selected = False

# Read state
is_checked = session.FindById("wnd[0]/usr/chkFLAG").selected
```

### Grids (ALV Tables) ★ Important

```python
# Access grid
grid = session.FindById("wnd[0]/usr/cntlCTRL/shellcont/shell")

# Grid properties
row_count = grid.rowCount
col_count = grid.columnCount
visible_rows = grid.visibleRowCount

# Read cell value
value = grid.getCellValue(row=0, col="MATNR")

# Modify cell
grid.modifyCell(row=0, col="MATNR", value="NEW-MAT-001")

# See [Grid & Table Operations](../02-practical-guides/grid-and-table-operations.md)
```

---

## Accessing Objects {#accessing}

### Pattern 1: Direct Path (Recommended)

```python
field = session.FindById("wnd[0]/usr/ctxtMATNR")
field.text = "TEST"
```

**Advantages:**
- Fast once you know the ID
- Easy to understand
- Cached by SAP if element hasn't changed

### Pattern 2: Chain Access

```python
main_window = session.FindById("wnd[0]")
user_area = main_window  # User area is implicit parent
field = session.FindById("wnd[0]/usr/ctxtMATNR")
```

### Pattern 3: Relative IDs (Advanced)

```python
# Relative ID (from current window)
# Only works from GuiComponent, not GuiSession
field = session.FindById("wnd[0]/usr/ctxtMATNR")

# Relative access (less common)
# field.Parent gives you parent object
```

### Safe Access Pattern (Recommended for Production)

```python
def get_field_safe(session, field_id, default_value=""):
    """Safely get field value with error handling"""
    try:
        field = session.FindById(field_id)
        if field and hasattr(field, 'text'):
            return field.text
    except Exception as e:
        print(f"Field {field_id} not found: {e}")
    
    return default_value

def set_field_safe(session, field_id, value):
    """Safely set field value with error handling"""
    try:
        field = session.FindById(field_id)
        if field and hasattr(field, 'text') and field.changeable:
            field.text = str(value)
            return True
    except Exception as e:
        print(f"Failed to set {field_id}: {e}")
    
    return False

# Usage
material = get_field_safe(session, "wnd[0]/usr/ctxtMATNR", "")
set_field_safe(session, "wnd[0]/usr/ctxtMATNR", "TEST-001")
```

---

**Next Reading:**
- [SAP GUI Launcher & Smart Connection](02-sap-gui-launcher.md) — Open SAP & find sessions programmatically
- [Quick Reference — Virtual Keys](../01-quick-reference/virtual-keys.md) — Key codes for SendVKey()
- [Practical Guides — Grid Operations](../02-practical-guides/grid-and-table-operations.md) — ALV grids in detail
