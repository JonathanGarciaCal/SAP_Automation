# Architecture Patterns

## The COM Bridge Pattern (Core Architecture)

### The Problem

NiceGUI runs an asyncio event loop on the main thread. SAP GUI COM objects are apartment-threaded and blocking. Calling COM directly from the async loop would freeze the entire UI.

### The Solution: Command Queue + Dedicated COM Thread

```
┌─────────────────────────────┐        ┌─────────────────────────────┐
│   Main Thread (async loop)  │        │  COM Worker Thread (STA)    │
│                             │        │                             │
│  NiceGUI UI handlers        │        │  pythoncom.CoInitialize()   │
│  ├─ on_click callbacks      │        │  session = GetObject(...)   │
│  ├─ ui.timer callbacks      │        │                             │
│  └─ page rendering          │        │  while True:                │
│                             │        │    cmd = queue.get()        │
│  async def on_execute():    │        │    result = execute(cmd)    │
│    future = loop.create_    │  Queue │    future.set_result(...)   │
│      future()               │──────► │                             │
│    queue.put(Command(...,   │        │                             │
│      future))               │        │                             │
│    result = await future    │◄────── │  (resolves via              │
│    update_ui(result)        │        │   call_soon_threadsafe)     │
│                             │        │                             │
└─────────────────────────────┘        └─────────────────────────────┘
```

### Key Design Decisions

1. **Single COM thread**: Only one thread ever touches COM objects. No locking needed.
2. **Command objects are serializable**: The queue carries method names and primitive arguments — never COM object references.
3. **Futures bridge async↔sync**: The main thread creates an `asyncio.Future`, passes it in the command, and `await`s it. The COM thread resolves it via `loop.call_soon_threadsafe()`.
4. **Timeouts**: The `await` on the future can have a timeout to handle hung SAP operations.

### Alternative Considered: Custom ThreadPoolExecutor

Instead of a dedicated thread with a queue, you could use NiceGUI's `run.io_bound` with a custom executor that initializes COM:

```python
import concurrent.futures
import pythoncom

class COMThreadPoolExecutor(concurrent.futures.ThreadPoolExecutor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, max_workers=1, **kwargs)  # Single thread!

    def _initializer(self):
        pythoncom.CoInitialize()
```

This is simpler but less flexible — you can't maintain state (like a session reference) across calls as easily. The dedicated thread pattern is recommended for this project.

---

## Configuration Schema (YAML)

### config.yaml
```yaml
# Application settings
app:
  host: "127.0.0.1"          # Bind address (use 0.0.0.0 only with auth!)
  port: 8080
  title: "SAP GUI Bridge"
  dark_mode: false

# SAP connection settings
sap:
  connection_index: 0         # Which SAP connection to attach to (0 = first)
  session_index: 0            # Which session within the connection (0 = first)
  heartbeat_interval: 5       # Seconds between liveness checks
  auto_reconnect: true        # Auto-retry on disconnection
  command_timeout: 120        # Max seconds for a single SAP operation

# Export settings
export:
  default_folder: "C:\\SAP_Exports"
  csv_delimiter: ";"
  excel_engine: "openpyxl"
  timestamp_filenames: true   # Append timestamp to filenames

# Script settings
scripts:
  directory: "./scripts"      # Where to find Python script files
  auto_discover: true         # Auto-scan directory for new scripts

# Logging
logging:
  level: "INFO"               # DEBUG, INFO, WARNING, ERROR
  file: "./logs/bridge.log"
  max_bytes: 10485760         # 10 MB per log file
  backup_count: 5             # Keep 5 rotated log files
```

### reports.yaml
```yaml
reports:
  - name: "Warehouse Stocks"
    description: "Material stocks by plant and storage location"
    transaction: "MB52"
    fields:
      - id: "wnd[0]/usr/ctxtMATNR-LOW"
        label: "Material Number"
        type: "text"
        required: false
      - id: "wnd[0]/usr/ctxtWERKS-LOW"
        label: "Plant"
        type: "text"
        required: true
        default: "1000"
    execute_key: 8              # F8 to execute
    output_type: "grid"         # "grid" or "clipboard"
    export_format: "xlsx"
    export_folder: "C:\\SAP_Exports\\MB52"

  - name: "Purchase Orders"
    description: "Open purchase orders by vendor"
    transaction: "ME2M"
    variant: "/DEFAULT_REPORT"  # Use saved variant
    fields:
      - id: "wnd[0]/usr/ctxtLIFNR-LOW"
        label: "Vendor"
        type: "text"
        required: false
    execute_key: 8
    output_type: "grid"
    export_format: "csv"
    export_folder: "C:\\SAP_Exports\\ME2M"
```

---

## Error Recovery Flow

```
SAP COM Call
    │
    ├─► Success → return result
    │
    └─► pywintypes.com_error
            │
            ├─► "Control not found" (619)
            │       → Log warning
            │       → Return error to UI: "Element not found — screen may have changed"
            │
            ├─► "Object disconnected" / "Call rejected"
            │       → Set alive = False
            │       → Notify UI: "SAP session lost"
            │       → If auto_reconnect:
            │           → Wait 3 seconds
            │           → Try GetObject("SAPGUI") again
            │           → Re-enumerate connections/sessions
            │           → If reconnected: notify UI "Reconnected"
            │           → If failed: retry up to 5 times, then give up
            │
            ├─► "CoInitialize not called"
            │       → BUG — COM called from wrong thread
            │       → Log error, crash loudly (this is a coding error)
            │
            └─► Unknown error
                    → Log full error details
                    → Return error to UI with raw message
                    → Do not crash — let user retry
```
