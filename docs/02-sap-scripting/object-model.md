# SAP GUI Scripting — Object Model

## Runtime Hierarchy

The SAP GUI Scripting API represents the entire SAP GUI as a tree of COM objects. The root is `GuiApplication` and every visible element on screen is a node in this tree.

```
GuiApplication                              # Root: the SAP GUI process (SAPlogon)
│
├─ GuiConnection[0]                         # First SAP system connection
│  ├─ GuiSession[0]                         # First session/window on this connection
│  │  ├─ GuiSessionInfo                     # Read-only info: system, client, user, transaction
│  │  ├─ GuiMainWindow (wnd[0])             # Primary window
│  │  │  ├─ GuiTitlebar (titl)
│  │  │  ├─ GuiToolbar (tbar[0])            # System toolbar
│  │  │  │  ├─ GuiOkCodeField (okcd)        # Transaction/command input field
│  │  │  │  ├─ GuiButton (btn[0])           # Enter
│  │  │  │  ├─ GuiButton (btn[3])           # Back
│  │  │  │  ├─ GuiButton (btn[15])          # Create session
│  │  │  │  └─ ...
│  │  │  ├─ GuiToolbar (tbar[1])            # Application toolbar
│  │  │  │  ├─ GuiButton (btn[8])           # Execute (F8)
│  │  │  │  └─ ...
│  │  │  ├─ GuiUserArea (usr)               # ★ Main content area
│  │  │  │  ├─ GuiTextField (txt...)        # Input/display text fields
│  │  │  │  ├─ GuiCTextField (ctxt...)      # Fields with F4 search help
│  │  │  │  ├─ GuiPasswordField (pwd...)    # Password fields
│  │  │  │  ├─ GuiLabel (lbl...)            # Read-only labels
│  │  │  │  ├─ GuiButton (btn...)           # Push buttons
│  │  │  │  ├─ GuiCheckBox (chk...)         # Checkboxes
│  │  │  │  ├─ GuiRadioButton (rad...)      # Radio buttons
│  │  │  │  ├─ GuiComboBox (cmb...)         # Dropdown lists
│  │  │  │  ├─ GuiTableControl (tbl...)     # Classic dynpro tables
│  │  │  │  │  ├─ GuiTableColumn[]
│  │  │  │  │  └─ GuiTableRow[]
│  │  │  │  ├─ GuiCustomControl → GuiContainerShell
│  │  │  │  │  └─ GuiGridView (shell)       # ★ ALV grid (most important for data)
│  │  │  │  ├─ GuiTabStrip (tabs...)        # Tab strip container
│  │  │  │  │  └─ GuiTab (tab...)           # Individual tabs
│  │  │  │  ├─ GuiTree (shell...)           # Tree controls
│  │  │  │  ├─ GuiScrollContainer (ssub...) # Scrollable subscreens
│  │  │  │  ├─ GuiSimpleContainer (sub...)  # Non-scrollable subscreens
│  │  │  │  ├─ GuiTextEdit (shell...)       # Multi-line text editor
│  │  │  │  └─ GuiHTMLViewer (shell...)     # Embedded HTML viewer
│  │  │  ├─ GuiMenubar (mbar)
│  │  │  │  └─ GuiMenu (menu[0..n])         # Top-level menus
│  │  │  │     └─ GuiMenu (menu[0..n])      # Submenus
│  │  │  ├─ GuiStatusbar (sbar)
│  │  │  │  └─ GuiStatusPane (pane[0..n])
│  │  │  └─ GuiGosShell (shellcont)         # Generic Object Services (only in New Visual Design)
│  │  │
│  │  └─ GuiModalWindow (wnd[1], wnd[2]...) # Pop-up dialogs
│  │     ├─ GuiUserArea (usr)
│  │     └─ GuiToolbar (tbar[0])
│  │
│  └─ GuiSession[1]                         # Second session on same connection
│
└─ GuiConnection[1]                         # Second SAP system connection
   └─ ...
```

## Base Interfaces

Every object in the tree inherits from one or more base interfaces:

### GuiComponent (all objects)
- `.Id` — Full path ID (e.g., `"/app/con[0]/ses[0]/wnd[0]/usr/txtFIELD"`)
- `.Name` — Short name (e.g., `"txtFIELD"`)
- `.Type` — Type string (e.g., `"GuiTextField"`, `"GuiGridView"`)
- `.TypeAsNumber` — Numeric type code
- `.Parent` — Parent object in the hierarchy
- `.ContainerType` — Whether this object can have children

### GuiVComponent (visual objects)
All of GuiComponent, plus:
- `.Text` — The text content (readable and often writable)
- `.Changeable` — Whether the element is enabled and editable
- `.Modified` — Whether the user changed the value
- `.SetFocus()` — Move cursor focus to this element
- `.Visualize(on)` — Highlight with red border (True) or remove highlight (False)
- `.DumpState(innerObject)` — Dump detailed state information
- `.Height`, `.Width`, `.Left`, `.Top` — Position and size in pixels
- `.ScreenLeft`, `.ScreenTop` — Absolute screen coordinates

### GuiVContainer (containers with visual children)
All of GuiVComponent, plus:
- `.Children` — Collection of child objects
- `.FindById(id, raise=True)` — Find descendant by ID path
- `.FindByName(name, type)` — Find first child matching name and type
- `.FindByNameEx(name, type)` — Like FindByName but searches recursively

### GuiContainer (non-visual containers)
Like GuiVContainer but for administrative objects (connections, sessions).

## Accessing the Tree from Python

```python
import win32com.client

# Attach to running SAP GUI
SapGuiAuto = win32com.client.GetObject("SAPGUI")
application = SapGuiAuto.GetScriptingEngine    # GuiApplication

# Navigate the tree
connection = application.Children(0)            # First GuiConnection
session = connection.Children(0)                # First GuiSession
window = session.FindById("wnd[0]")            # GuiMainWindow
user_area = session.FindById("wnd[0]/usr")     # GuiUserArea

# Read session info
print(session.Info.SystemName)    # e.g., "PRD"
print(session.Info.Client)        # e.g., "100"
print(session.Info.User)          # e.g., "SAPUSER"
print(session.Info.Transaction)   # e.g., "SESSION_MANAGER"
```

## Walking the Tree Recursively

This is the pattern the Screen Inspector will use:

```python
def walk_element(element, depth=0):
    """Recursively walk the SAP GUI element tree"""
    info = {
        'id': element.Id,
        'name': element.Name,
        'type': element.Type,
        'text': '',
        'changeable': False,
    }

    # Try to read visual properties (not all objects have them)
    try:
        info['text'] = element.Text
    except:
        pass
    try:
        info['changeable'] = element.Changeable
    except:
        pass

    print("  " * depth + f"{info['type']}: {info['name']} = {info['text']!r}")

    # Recurse into children if this is a container
    try:
        for i in range(element.Children.Count):
            child = element.Children(i)
            walk_element(child, depth + 1)
    except:
        pass  # Not a container, or children not accessible

# Usage:
walk_element(session.FindById("wnd[0]"))
```

## Object Type Prefixes

The `Name` property of each object starts with a type prefix:

| Prefix | Object Type | Description |
|--------|-------------|-------------|
| `txt` | GuiTextField | Input/display text field |
| `ctxt` | GuiCTextField | Text field with F4 search help |
| `pwd` | GuiPasswordField | Password input |
| `lbl` | GuiLabel | Read-only label |
| `btn` | GuiButton | Push button |
| `chk` | GuiCheckBox | Checkbox |
| `rad` | GuiRadioButton | Radio button |
| `cmb` | GuiComboBox | Dropdown list |
| `tbl` | GuiTableControl | Classic dynpro table |
| `tabs` | GuiTabStrip | Tab strip container |
| `tab` | GuiTab | Individual tab |
| `sub` | GuiSimpleContainer | Non-scrollable subscreen |
| `ssub` | GuiScrollContainer | Scrollable subscreen |
| `shell` | GuiShell | Generic shell (GridView, Tree, etc.) |
| `shellcont` | GuiContainerShell | Container for shell controls |
| `titl` | GuiTitlebar | Window title bar |
| `wnd` | GuiMainWindow/GuiModalWindow | Window |
| `usr` | GuiUserArea | Main content area |
| `mbar` | GuiMenubar | Menu bar |
| `menu` | GuiMenu | Menu / submenu |
| `sbar` | GuiStatusbar | Status bar |
| `okcd` | GuiOkCodeField | Transaction command field |
