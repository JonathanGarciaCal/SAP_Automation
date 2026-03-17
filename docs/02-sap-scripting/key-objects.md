# Key SAP GUI Scripting Objects

## GuiSession

The central object for all interaction with a single SAP window.

### Properties
| Property | Type | Description |
|----------|------|-------------|
| `Info.SystemName` | String | SAP system ID (e.g., "PRD") |
| `Info.Client` | String | Client number (e.g., "100") |
| `Info.User` | String | Logged-in user ID |
| `Info.Transaction` | String | Current transaction code |
| `Info.Program` | String | Current ABAP program name |
| `Info.Dynpro` | String | Current dynpro/screen number |
| `Info.ApplicationServer` | String | Application server hostname |
| `Info.Language` | String | Login language |
| `Info.SessionNumber` | Integer | Session index |
| `Info.IsLowSpeedConnection` | Boolean | Low-speed mode active |
| `ActiveWindow` | GuiFrameWindow | Currently active window (main or modal) |
| `Busy` | Boolean | True while SAP processes a server roundtrip |
| `Children` | Collection | All windows in this session |
| `Record` | Boolean | Whether recording is active |
| `TestToolMode` | Integer | 0=off, 1=read-only test tool |

### Methods
| Method | Description |
|--------|-------------|
| `StartTransaction("SE16")` | Navigate to transaction (replaces current) |
| `SendCommand("/nSE16")` | Execute OK code (same as typing in command field + Enter) |
| `EndTransaction()` | End current transaction (like /n) |
| `CreateSession()` | Open a new SAP session window |
| `FindById(id, raise=True)` | Find element by full or relative ID. If `raise=False`, returns `None` instead of throwing. |
| `FindByName(name, type)` | Find first element matching name and type |
| `LockSessionUI()` / `UnlockSessionUI()` | Lock/unlock the session to prevent user interaction during script |

---

## GuiMainWindow

The primary window: `session.FindById("wnd[0]")`

### Key Methods
| Method | Description |
|--------|-------------|
| `SendVKey(key)` | Simulate a keyboard press (see SendVKey Reference) |
| `Maximize()` | Maximize window |
| `Iconify()` | Minimize to taskbar |
| `Restore()` | Restore from minimized |
| `ResizeWorkingPane(w, h, innerResize)` | Resize the working area |
| `Close()` | Close the window |

### Key Properties
| Property | Description |
|----------|-------------|
| `SystemFocus` | Element that has keyboard focus |
| `Text` | Window title text |
| `WorkingPaneHeight/Width` | Size of the working area in character metric |
| `Handle` | Win32 window handle (HWND) |

---

## GuiGridView (ALV Grid) ★ Most Important for Data Extraction

Accessed via: `session.FindById("wnd[0]/usr/cntlCONTROL/shellcont/shell")`

The exact path varies per transaction — use Scripting Tracker to find it.

### Properties
| Property | Type | Description |
|----------|------|-------------|
| `RowCount` | Long | Total number of data rows |
| `ColumnCount` | Long | Number of columns |
| `VisibleRowCount` | Long | Rows visible on screen |
| `FirstVisibleRow` | Long | Index of first visible row (writable — use for scrolling) |
| `ColumnOrder` | Variant (Array) | Array of column technical names in display order |
| `SelectedRows` | String | Comma-separated list of selected row indices |
| `CurrentCellRow` | Long | Row of the current cell |
| `CurrentCellColumn` | String | Column name of the current cell |
| `Title` | String | Grid title text |

### Methods — Reading Data
| Method | Returns | Description |
|--------|---------|-------------|
| `GetCellValue(row, col)` | String | Read cell value. `row` is integer index, `col` is column technical name (string). |
| `GetCellTooltip(row, col)` | String | Read cell tooltip |
| `GetCellColor(row, col)` | Long | Cell background color |
| `GetCellState(row, col)` | String | Cell edit state |
| `GetColumnTitles(col)` | Collection | Column header text(s) |
| `GetColumnDataType(col)` | String | ABAP data type of column |
| `IsColumnFiltered(col)` | Boolean | Whether a filter is active on this column |
| `IsCellEditable(row, col)` | Boolean | Whether the cell can be edited |

### Methods — Interaction
| Method | Description |
|--------|-------------|
| `ModifyCell(row, col, value)` | Write to a cell |
| `SetCurrentCell(row, col)` | Set cursor position |
| `DoubleClickCurrentCell()` | Double-click the current cell |
| `ClickCurrentCell()` | Single-click the current cell |
| `SelectAll()` | Select all rows |
| `DeselectAll()` | Clear selection |
| `SelectColumn(col)` | Select entire column |
| `ContextMenu()` | Open right-click context menu |
| `PressToolbarButton(id)` | Press ALV toolbar button |
| `PressToolbarContextButton(id)` | Open toolbar dropdown button |
| `PressEnter()` | Press Enter on the grid |

### Data Extraction Pattern (Python)
```python
def extract_grid_data(session, grid_id):
    """Extract all data from an ALV grid"""
    grid = session.FindById(grid_id)
    columns = list(grid.ColumnOrder)
    rows = []

    for row_idx in range(grid.RowCount):
        row_data = {}
        for col in columns:
            row_data[col] = grid.GetCellValue(row_idx, col)
        rows.append(row_data)

    return columns, rows
```

### Fast Extraction via Clipboard (for large grids)
```python
def extract_grid_clipboard(session, grid_id):
    """Fast extraction using clipboard — much faster for 1000+ rows"""
    import win32clipboard

    grid = session.FindById(grid_id)
    grid.SelectAll()
    grid.ContextMenu()
    # Navigate context menu to copy (varies by SAP version)
    # Or use keyboard shortcut:
    session.FindById("wnd[0]").SendVKey(24)  # Ctrl+C in some contexts

    win32clipboard.OpenClipboard()
    try:
        data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()

    # Parse tab-separated data
    lines = data.strip().split('\n')
    headers = lines[0].split('\t')
    rows = [dict(zip(headers, line.split('\t'))) for line in lines[1:]]
    return headers, rows
```

---

## GuiTableControl (Classic Dynpro Table)

Accessed via: `session.FindById("wnd[0]/usr/tblTABLENAME")`

Older-style table, different API from ALV GridView.

### Properties
| Property | Type | Description |
|----------|------|-------------|
| `RowCount` | Long | Number of visible rows on screen |
| `VisibleRowCount` | Long | Same as RowCount for classic tables |
| `Columns` | Collection | `GuiTableColumn` objects |
| `Rows` | Collection | `GuiTableRow` objects |
| `VerticalScrollbar.Position` | Long | Current scroll position |
| `VerticalScrollbar.Maximum` | Long | Maximum scroll value |
| `HorizontalScrollbar.Position/Maximum` | Long | Horizontal scroll |

### Data Extraction Pattern
```python
def extract_table_control(session, table_id):
    """Extract data from a classic table control"""
    table = session.FindById(table_id)
    columns = []
    for i in range(table.Columns.Count):
        columns.append(table.Columns(i).Name)

    all_rows = []
    scroll_pos = 0
    while True:
        table.VerticalScrollbar.Position = scroll_pos
        empty_row_count = 0

        for row_idx in range(table.VisibleRowCount):
            row_data = {}
            row = table.GetAbsoluteRow(scroll_pos + row_idx)
            all_empty = True
            for col_idx, col_name in enumerate(columns):
                try:
                    cell = row.FindById(col_name)  # or use index
                    row_data[col_name] = cell.Text
                    if cell.Text.strip():
                        all_empty = False
                except:
                    row_data[col_name] = ""

            if all_empty:
                empty_row_count += 1
            else:
                all_rows.append(row_data)

        scroll_pos += table.VisibleRowCount
        if scroll_pos > table.VerticalScrollbar.Maximum or empty_row_count > 3:
            break

    return columns, all_rows
```

---

## GuiModalWindow

Pop-up dialog: `session.FindById("wnd[1]")` (or `wnd[2]`, etc.)

### Detection Pattern
```python
def check_for_modal(session):
    """Check if a modal dialog has appeared"""
    try:
        active = session.ActiveWindow
        if active.Type == "GuiModalWindow":
            return {
                'type': 'modal',
                'title': active.Text,
                'message': read_modal_message(session),
                'window_id': active.Id,
            }
    except:
        pass
    return None

def read_modal_message(session):
    """Try to read the message text from a modal dialog"""
    for msg_id in ['wnd[1]/usr/txtMESSTXT1', 'wnd[1]/usr/txtSPOP-TEXTLINE1',
                    'wnd[1]/usr/txtSPOP-TEXTLINE2']:
        try:
            return session.FindById(msg_id).Text
        except:
            continue
    # Fallback: try to read the statusbar
    try:
        return session.FindById("wnd[1]/sbar").Text
    except:
        return "(could not read message)"

def dismiss_modal(session, button_index=0):
    """Dismiss a modal by pressing a button (0=first button, usually OK/Continue)"""
    try:
        session.FindById(f"wnd[1]/tbar[0]/btn[{button_index}]").Press()
    except:
        session.FindById("wnd[1]").SendVKey(0)  # Fallback: press Enter
```

---

## GuiStatusbar

The bottom bar showing messages: `session.FindById("wnd[0]/sbar")`

### Properties
| Property | Type | Description |
|----------|------|-------------|
| `.Text` | String | Message text |
| `.MessageType` | String | `"S"` (Success), `"W"` (Warning), `"E"` (Error), `"I"` (Info), `"A"` (Abort) |

### Reading status after an action
```python
def get_status_message(session):
    sbar = session.FindById("wnd[0]/sbar")
    return {
        'text': sbar.Text,
        'type': sbar.MessageType,  # S, W, E, I, A
    }
```
