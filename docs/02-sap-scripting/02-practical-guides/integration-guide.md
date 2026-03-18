# Integration Guide: Using New SAP Components Together

## Overview

This guide shows how to integrate the new SAP automation components (`session_manager`, `connection_manager`, `session_display`, `performance`) into your workflow. These components are designed to work together seamlessly.

**Quick Summary:**
- **connection_manager**: Smart SAP launch and connection with automatic retry
- **session_manager**: Find and validate SAP sessions across multiple systems
- **session_display**: Export and monitor active sessions
- **performance**: Optimize script execution with adaptive waits and batch operations

---

## 1. Configuration Setup

### Add to config.yaml

The new components use these parameters in your config:

```yaml
sap:
  logon_path: "C:\\Program Files\\SAP\\FrontEnd\\SAP GUI\\saplogon.ini"
  username: "DEMO"
  password: ${SAP_PASSWORD}  # Use env variable
  client: "100"
  lang: "EN"
  sapgui_exe_path: "C:\\Program Files\\SAP\\FrontEnd\\SAP GUI\\saplogon.exe"
  connection_timeout_sec: 30        # Max seconds to wait for connection
  wait_optimization_enabled: true   # Use SmartWait for 60-70% speedup
  retry_attempts: 3                 # Connection retry attempts
  retry_backoff_sec: 2              # Initial retry backoff (exponential: 2, 4, 8...)
```

### Environment Variables (Optional)

Override config values with environment variables:

```bash
# Optional: Override connection timeout
set SAP_CONNECTION_TIMEOUT_SEC=60

# Optional: Override retry attempts
set SAP_RETRY_ATTEMPTS=5

# Optional: Disable wait optimization
set SAP_WAIT_OPTIMIZATION_ENABLED=false

# Optional: SAP password (NEVER hardcode)
set SAP_PASSWORD=YourPassword
```

---

## 2. Basic Connection Flow

### Scenario: Connect to SAP, Execute Transaction

```python
from config import get_config
from sap.connection_manager import smart_connect
from sap.performance import SmartWait

# Load configuration
config = get_config()

# Smart connect with automatic launch if needed
try:
    session = smart_connect(
        system="PRD",
        client="100",
        auto_launch=True
    )
    print(f"Connected to {session.SystemName}")
    
    # Start transaction
    session.StartTransaction("VA01")
    
    # Use SmartWait instead of fixed sleep
    SmartWait.after_screen_load()
    
    # Interact with SAP...
    
except Exception as e:
    print(f"Connection failed: {e}")
```

**Key Points:**
- `smart_connect()` automatically detects if SAP is running
- If not running, it launches SAP (if path is configured)
- Retries with exponential backoff on failure
- Timeout is configurable (`connection_timeout_sec`)

---

## 3. Multi-Session Management

### Scenario: Work with Multiple Systems (PRD, DEV, QAS)

```python
from sap.session_manager import SAP_Session_Manager
from sap.session_display import SessionDisplayManager

# Initialize managers
session_mgr = SAP_Session_Manager()
display_mgr = SessionDisplayManager()

# List all active sessions
all_sessions = session_mgr.get_all_sessions()
print(session_mgr.format_sessions_table(all_sessions))

# Output:
# #  | SystemName | Client | UserId | Transaction | Program
# ---|-------------|--------|--------|-------------|----------
# 0  | PRD         | 100    | DEMO   | VA01        | SAPLIQU01
# 1  | DEV         | 200    | DEMO   | MM01        | SAPLIQU02
# 2  | QAS         | 300    | DEMO   | IW31        | SAPLIWF01

# Get specific session
prd_session = session_mgr.get_session_by_system_client("PRD", "100")
if prd_session:
    print(f"Found: {prd_session.SystemName}")

# Validate session is alive
if session_mgr.validate_session(prd_session):
    print("Session is active")
else:
    print("Session disconnected")

# Export current sessions to CSV
display_mgr.export_sessions_csv("active_sessions.csv")
```

---

## 4. Batch Operations for Speed

### Scenario: Set Multiple Fields Rapidly

**SLOW (25 seconds):**
```python
# Per-field waits = slow
session.FindById("wnd[0]/usr/ctxtVBELN").Text = "100001"
time.sleep(2)  # Wait after each field

session.FindById("wnd[0]/usr/ctxtVPOS").Text = "001"
time.sleep(2)

session.FindById("wnd[0]/usr/ctxtVMENG").Text = "10"
time.sleep(2)
# ... total 20 seconds for 10 fields
```

**FAST (3 seconds with batch ops):**
```python
from sap.performance import BatchOperations, SmartWait

fields = {
    "wnd[0]/usr/ctxtVBELN": "100001",
    "wnd[0]/usr/ctxtVPOS": "001",
    "wnd[0]/usr/ctxtVMENG": "10",
    "wnd[0]/usr/ctxtVMAT": "PART-123",
    "wnd[0]/usr/ctxtVWERK": "1000",
    "wnd[0]/usr/ctxtVLGORT": "01",
    "wnd[0]/usr/ctxtVSERTY": "ZPROD",
}

# Set all fields at once, wait once at end
BatchOperations.batch_set_fields(session, fields)

# Result: ~3 seconds total (8.3x speedup)
```

---

## 5. Adaptive Wait Strategy

### Scenario: Wait for Element Safely

**Traditional approach (risky):**
```python
# Fixed wait - what if network is slow?
time.sleep(2)
element = session.FindById("wnd[0]/usr/subSCREEN:SAPLVIM0:2400/ctxtVIRECT")
element.SetFocus()
```

**SmartWait approach (safe):**
```python
from sap.performance import SmartWait

# Wait intelligently - poll element every 0.1s until it exists
SmartWait.until_element_exists(
    session,
    "wnd[0]/usr/subSCREEN:SAPLVIM0:2400/ctxtVIRECT",
    timeout=10
)

# Use convenience wait after navigation
SmartWait.after_button_click()
element = session.FindById("wnd[0]/usr/subSCREEN:SAPLVIM0:2400/ctxtVIRECT")
element.SetFocus()

# Result: Typically 0.3-0.5s (vs fixed 2s = 4-6x faster)
```

**SmartWait timing reference:**
```python
SmartWait.TIMING = {
    'field_input': 0.2,       # After field setText()
    'button_click': 0.3,      # After button press
    'navigation': 0.5,        # After menu navigation
    'screen_load': 1.0,       # Major screen transition
    'table_refresh': 0.5,     # After table refresh
    'dialog': 0.8,            # After dialog open
}

# Use as: SmartWait.after_field_input()  # sleep 0.2s
#         SmartWait.after_button_click() # sleep 0.3s
```

---

## 6. Performance Benchmarking

### Scenario: Measure Optimization Impact

```python
from sap.performance import Benchmark

# Benchmark slow implementation
def slow_set_fields(session):
    fields = {"field1": "val1", "field2": "val2", ...}
    for field_id, value in fields.items():
        session.FindById(field_id).Text = value
        time.sleep(2)

# Benchmark fast implementation
def fast_set_fields(session):
    fields = {"field1": "val1", "field2": "val2", ...}
    BatchOperations.batch_set_fields(session, fields)

# Run comparison
Benchmark.compare(
    "slow_approach",
    "fast_approach",
    lambda: slow_set_fields(session),
    lambda: fast_set_fields(session),
    iterations=5
)

# Output:
# SLOW_APPROACH: 25.4s total, 5.1s avg
# FAST_APPROACH: 3.2s total, 0.64s avg
# Improvement: 7.9x faster
```

---

## 7. Error Handling & Retry

### Scenario: Robust Multi-System Sync

```python
from sap.connection_manager import SAPConnectionManager
from sap.session_manager import SAP_Session_Manager

config = get_config()
conn_mgr = SAPConnectionManager(config.sap.__dict__)
session_mgr = SAP_Session_Manager()

def sync_data_across_systems():
    """Read from PRD, sync to DEV and QAS with retries."""
    
    # Get or create PRD session (with smart retry)
    prd_session = conn_mgr.connect(
        system="PRD",
        client="100",
        auto_launch=True,
        timeout=30
    )
    
    if not session_mgr.validate_session(prd_session):
        raise RuntimeError("PRD session invalid")
    
    # Read data from PRD
    prd_session.StartTransaction("VA03")  # View sales order
    SmartWait.after_screen_load()
    
    # Read order number...
    order_data = {...}
    
    # Sync to DEV
    try:
        dev_session = conn_mgr.connect("DEV", "200", timeout=30)
        dev_session.StartTransaction("VA01")  # Create sales order
        SmartWait.after_screen_load()
        # Set fields with batch...
    except Exception as e:
        print(f"DEV sync failed: {e}")
    
    # Sync to QAS
    try:
        qas_session = conn_mgr.connect("QAS", "300", timeout=30)
        qas_session.StartTransaction("VA01")
        SmartWait.after_screen_load()
        # Set fields with batch...
    except Exception as e:
        print(f"QAS sync failed: {e}")

# Run with error handling
try:
    sync_data_across_systems()
except Exception as e:
    print(f"Sync failed: {e}")
```

---

## 8. Session Monitoring Dashboard

### Scenario: Monitor Active Sessions

```python
from sap.session_display import SessionDisplayManager

display_mgr = SessionDisplayManager()

# Display all sessions as ASCII table
print(display_mgr.get_sessions_ascii_table())

# Get detailed info
print(display_mgr.get_sessions_detailed())

# Statistics
print(f"Total sessions: {display_mgr.get_session_count_by_system()}")
print(display_mgr.get_session_summary())

# Export to CSV for analysis
display_mgr.export_sessions_csv("session_log.csv")

# Output example:
# Total sessions: {'PRD': 2, 'DEV': 1, 'QAS': 1, 'TST': 2}
# Session Summary:
#  - Total: 6 sessions
#  - Systems: PRD, DEV, QAS, TST
#  - Users: DEMO, SYSTEM, BATCH01
#  - Latest: 2024-01-15 14:32:15
```

---

## 9. Step-by-Step Workflow

### Complete Example: Automated Order Processing

```python
import os
from config import get_config
from sap.connection_manager import smart_connect
from sap.session_manager import SAP_Session_Manager
from sap.session_display import SessionDisplayManager
from sap.performance import SmartWait, BatchOperations, Benchmark

# 1. Setup
config = get_config()
session_mgr = SAP_Session_Manager()
display_mgr = SessionDisplayManager()

# 2. Monitor current sessions
print("Current sessions:")
for session in session_mgr.get_all_sessions():
    print(f"  {session['SystemName']}-{session['Client']}: {session['UserId']}")

# 3. Connect to PRD (with smart auto-launch)
try:
    prd_session = smart_connect("PRD", "100", auto_launch=True)
    print(f"Connected to {prd_session.SystemName}")
except Exception as e:
    print(f"Connection failed: {e}")
    exit(1)

# 4. Validate session
if not session_mgr.validate_session(prd_session):
    print("Session invalid")
    exit(1)

# 5. Execute transaction
prd_session.StartTransaction("VA01")  # Create Sales Order
SmartWait.after_screen_load()

# 6. Batch field entry (60-70% faster)
order_data = {
    "wnd[0]/usr/ctxtVBYLN": "ACME Inc",
    "wnd[0]/usr/ctxtVVDTU": "01.01.2024",
    "wnd[0]/usr/ctxtVPPR_DOC": "SO001",
}
BatchOperations.batch_set_fields(prd_session, order_data)

# 7. Submit transaction
prd_session.FindById("wnd[0]/tbtabSCREENSTATUS/btn[0]").Press()  # Save
SmartWait.after_button_click()

# 8. Benchmark result
print("Order created successfully")

# 9. Export session log
display_mgr.export_sessions_csv("execution_log.csv")

print("Done!")
```

---

## 10. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "SAP GUI is not running" | Enable `auto_launch=True` and set `sapgui_exe_path` in config |
| "Connection timeout" | Increase `connection_timeout_sec` or check network |
| "Element not found" | Use `SmartWait.until_element_exists()` instead of `time.sleep()` |
| "Element found but can't interact" | Check element ID with SAP Scripting Tracker recorder |
| "Batch operations fail" | Ensure all field IDs are valid before batch operation |
| "Performance not improved" | Check if `wait_optimization_enabled=true` in config |

---

## 11. Next Steps

1. **Update config.yaml** with new parameters
2. **Import smart_connect** in your main.py
3. **Replace time.sleep()** with SmartWait in existing scripts
4. **Use BatchOperations** for field setting
5. **Monitor with SessionDisplayManager** for production runs

---

## Reference: Quick Import Guide

```python
# Connection & Launch
from sap.connection_manager import SAPConnectionManager, smart_connect

# Session Management
from sap.session_manager import SAP_Session_Manager, get_session

# Session Display
from sap.session_display import SessionDisplayManager, display_sessions, export_sessions

# Performance Optimization
from sap.performance import SmartWait, BatchOperations, Benchmark
```

