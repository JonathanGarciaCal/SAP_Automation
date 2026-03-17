# Supporting Libraries Reference

> **Note**: For detailed openpyxl reference (Excel read/write/modify), see [openpyxl.md](openpyxl.md).

## PyRFC — Direct RFC Calls (Complementary to GUI Scripting)

### What It Is
PyRFC provides Python bindings for SAP NetWeaver RFC SDK, allowing direct ABAP function module calls without going through the GUI.

### When to Use (Instead of GUI Scripting)
- Bulk table reads (`RFC_READ_TABLE`) — much faster than navigating SE16
- Calling BAPIs for data manipulation
- Extracting master data, transactional data, or configuration tables
- Any case where you don't need to interact with a specific SAP screen

### When GUI Scripting Is Still Needed
- Running transactions that have complex screen flows
- Interacting with ALV reports that don't have a direct RFC equivalent
- Automating user-specific workflows (approval screens, custom transactions)
- Any screen-specific interaction

### Prerequisites
- SAP NetWeaver RFC SDK 7.50+ (download from SAP Software Download Center — needs S-user)
- Set `SAPNWRFC_HOME` environment variable to the SDK lib directory
- `pip install pyrfc`

### Basic Usage
```python
from pyrfc import Connection

# Connect directly to SAP (not through GUI)
conn = Connection(
    user='USERNAME',
    passwd='PASSWORD',
    ashost='sap-server.company.com',
    sysnr='00',
    client='100',
)

# Read a table
result = conn.call('RFC_READ_TABLE',
    QUERY_TABLE='MARA',           # Table name
    DELIMITER='|',                 # Field separator
    FIELDS=[                       # Which columns
        {'FIELDNAME': 'MATNR'},
        {'FIELDNAME': 'MTART'},
        {'FIELDNAME': 'MATKL'},
    ],
    OPTIONS=[                      # WHERE clause
        {'TEXT': "MTART EQ 'FERT'"},
    ],
    ROWCOUNT=1000,                 # Max rows
)

# Parse results
headers = [f['FIELDNAME'] for f in result['FIELDS']]
rows = [row['WA'].split('|') for row in result['DATA']]

conn.close()
```

### Links
- GitHub: `https://github.com/SAP-archive/PyRFC`
- PyPI: `https://pypi.org/project/pyrfc/`
- Docs: `https://pyrfc.readthedocs.io/`

---

## openpyxl — Excel Export

### Basic Excel File Creation
```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from datetime import datetime

def export_to_excel(data: list[dict], filepath: str, sheet_name: str = 'SAP Data'):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    if not data:
        wb.save(filepath)
        return

    # Header row
    headers = list(data[0].keys())
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    # Data rows
    for row_idx, row_data in enumerate(data, 2):
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=row_idx, column=col_idx, value=row_data.get(header, ''))

    # Auto-fit column widths (approximate)
    for col_idx, header in enumerate(headers, 1):
        max_len = len(header)
        for row in data[:100]:  # Sample first 100 rows
            val = str(row.get(header, ''))
            max_len = max(max_len, len(val))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 2, 50)

    # Freeze header row
    ws.freeze_panes = 'A2'

    # Auto-filter
    ws.auto_filter.ref = ws.dimensions

    wb.save(filepath)
```

### Links
- Docs: `https://openpyxl.readthedocs.io/`

---

## Pydantic + YAML — Configuration

### Config Model
```python
from pydantic import BaseModel, Field
from pathlib import Path
import yaml

class SAPConfig(BaseModel):
    connection_index: int = Field(default=0, description="Which SAP connection to attach to")
    session_index: int = Field(default=0, description="Which session within the connection")
    heartbeat_interval: float = Field(default=5.0, ge=1.0, le=60.0)
    command_timeout: float = Field(default=120.0, ge=10.0, le=600.0)
    auto_reconnect: bool = True

class ExportConfig(BaseModel):
    default_folder: Path = Path("C:/SAP_Exports")
    csv_delimiter: str = ";"
    timestamp_filenames: bool = True
    excel_engine: str = "openpyxl"

class ScriptsConfig(BaseModel):
    directory: Path = Path("./scripts")
    auto_discover: bool = True

class AppConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    title: str = "SAP GUI Bridge"
    dark_mode: bool = False
    sap: SAPConfig = SAPConfig()
    export: ExportConfig = ExportConfig()
    scripts: ScriptsConfig = ScriptsConfig()
    log_level: str = "INFO"
    log_file: Path = Path("./logs/bridge.log")

def load_config(path: str = "config.yaml") -> AppConfig:
    with open(path, 'r') as f:
        data = yaml.safe_load(f) or {}
    return AppConfig(**data)

def save_config(config: AppConfig, path: str = "config.yaml"):
    with open(path, 'w') as f:
        yaml.dump(config.model_dump(mode='json'), f, default_flow_style=False)
```

### Links
- Pydantic v2: `https://docs.pydantic.dev/latest/`
- PyYAML: `https://pyyaml.org/wiki/PyYAMLDocumentation`

---

## PyInstaller — Windows Packaging

### Basic Command
```bash
pip install pyinstaller
pyinstaller --name "SAP_GUI_Bridge" \
    --onedir \
    --hidden-import win32com \
    --hidden-import pythoncom \
    --hidden-import pywintypes \
    --hidden-import nicegui \
    --add-data "config.yaml;." \
    --add-data "scripts;scripts" \
    --add-data "reports.yaml;." \
    main.py
```

### Gotchas
- NiceGUI bundles static web assets — make sure they're included (NiceGUI has PyInstaller support built in, check their docs for the latest recipe)
- `pywin32` DLLs must be included — `--hidden-import` usually handles this
- Config files and script directories need `--add-data`
- Test the packaged `.exe` on a clean machine (no Python installed)
- The resulting folder can be compressed to a `.zip` for distribution

### Links
- PyInstaller: `https://pyinstaller.org/en/stable/`

---

## win32clipboard — Fast Data Extraction

```python
import win32clipboard
import win32con

def get_clipboard_text() -> str:
    """Read text from Windows clipboard"""
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
            return win32clipboard.GetClipboardData(win32con.CF_TEXT).decode('utf-8')
        return ""
    finally:
        win32clipboard.CloseClipboard()

def parse_tab_separated(text: str) -> tuple[list[str], list[dict]]:
    """Parse tab-separated clipboard data into headers + rows"""
    lines = text.strip().split('\n')
    if not lines:
        return [], []
    headers = [h.strip() for h in lines[0].split('\t')]
    rows = []
    for line in lines[1:]:
        values = [v.strip() for v in line.split('\t')]
        if len(values) == len(headers):
            rows.append(dict(zip(headers, values)))
    return headers, rows
```
