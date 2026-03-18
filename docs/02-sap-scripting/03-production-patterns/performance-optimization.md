# Performance Optimization — Speed Up SAP Automation 2-3×

Learn proven optimization techniques to reduce runtime from minutes to seconds.

## Table of Contents

1. [Quick Wins](#quick-wins) (60–70% speedup possible)
2. [Wait Time Optimization](#waits) (Smart waits vs. fixed delays)
3. [Batch Operations](#batch) (Process multiple records)
4. [Benchmarking](#benchmarking) (Measure before/after)

---

## Quick Wins {#quick-wins}

### Reduce Unnecessary Waits

**Before (SLOW):**
```python
session.FindById("wnd[0]/usr/ctxtFIELD").Text = "value"
time.sleep(2)  # Too long!
session.FindById("wnd[0]/tbar[0]/btn[0]").Press()
time.sleep(2)  # Too long!
```

**After (FAST):**
```python
session.FindById("wnd[0]/usr/ctxtFIELD").Text = "value"
time.sleep(0.3)  # Just enough for SAP to process
session.FindById("wnd[0]/tbar[0]/btn[0]").Press()
time.sleep(0.5)  # Button needs a bit more
```

**Impact:** 60–70% faster (most of this overhead is wait time)

### Disable Notifications

**SAP Options:**
- Options → Accessibility and Scripting → Scripting
- ☐ Uncheck "Notify when scripting window is active"

**Server Parameter (RZ11):**
```
sapgui/user_scripting_force_notification = FALSE
```

**Impact:** Eliminates pop-up delays (0.5–1 sec per operation)

### Clean Up Recorded Macros

**Recorded (generated artifacts — slow):**
```python
session.FindById("wnd[0]").ResizeWorkingPane(173, 36, 0)
session.FindById("wnd[0]/tbar[0]/okcd").CaretPosition = 5
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nMM01"
```

**Optimized (remove GUI noise):**
```python
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nMM01"
```

**Impact:** Smaller script, slightly faster (psychological & real)

---

## Wait Time Optimization {#waits}

### Smart Wait Strategy

```python
import time

class SmartWait:
    """Adaptive wait times based on operation type"""
    
    # Tuned for typical SAP systems (adjust for your environment)
    TIMING = {
        'field_input': 0.2,        # Setting a text field
        'button_click': 0.3,       # Clicking button
        'navigation': 0.5,         # Changing transaction  (/nMM01)
        'screen_load': 1.0,        # New screen loading
        'grid_operation': 0.3,     # Grid cell modification
        'dialog_open': 0.7,        # Dialog appearance
        'table_scroll': 0.2,       # Scrolling table
    }
    
    @staticmethod
    def after_field_input():
        time.sleep(SmartWait.TIMING['field_input'])
    
    @staticmethod
    def after_button_click():
        time.sleep(SmartWait.TIMING['button_click'])
    
    @staticmethod
    def after_navigation():
        time.sleep(SmartWait.TIMING['navigation'])
    
    @staticmethod
    def after_screen_load():
        time.sleep(SmartWait.TIMING['screen_load'])
    
    @staticmethod
    def until_element_exists(session, element_id, timeout=10):
        """
        Wait for element to appear (not a fixed time).
        Better than time.sleep() because it returns immediately
        once element exists.
        """
        
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                elem = session.FindById(element_id)
                if elem:
                    return True
            except:
                pass
            
            time.sleep(0.1)
        
        return False

# Usage
def process_transaction_optimized(session):
    """Example with smart waits"""
    
    session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nMM01"
    session.FindById("wnd[0]").SendVKey(0)
    SmartWait.after_navigation()
    
    # Wait for screen to load (adaptive — not fixed 2 seconds)
    if SmartWait.until_element_exists(session, "wnd[0]/usr/ctxtMATNR", timeout=10):
        print("✓ Screen loaded")
    else:
        print("✗ Screen did not load in time")

# Typical runtime improvement: 30–50% faster than fixed waits
```

### Wait for SAP to Finish Processing

```python
import time

def wait_for_sap_ready(session, timeout=30):
    """
    Wait for SAP to finish processing a server roundtrip.
    Use instead of blind time.sleep() after navigation.
    """
    
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            window = session.FindById("wnd[0]")
            
            # When Busy transitions from True → False, screen is ready
            if not window.Busy:
                return True
            
            time.sleep(0.1)
        
        except:
            time.sleep(0.1)
    
    return False

# Usage
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nMM01"
session.FindById("wnd[0]").SendVKey(0)

if wait_for_sap_ready(session, timeout=10):
    print("✓ Screen ready")
    # Now safe to access elements
else:
    print("✗ SAP not responding")
```

---

## Batch Operations {#batch}

### Batch Set Multiple Fields (30% faster)

```python
def batch_set_fields(session, field_dict):
    """
    Set multiple fields without waiting between each.
    SAP is fast enough to process them together.
    """
    
    for field_id, value in field_dict.items():
        session.FindById(field_id).Text = str(value)
        # No sleep between fields — let SAP batch them
    
    # One wait at the end
    time.sleep(0.3)

# Usage - Before (slow)
session.FindById("wnd[0]/usr/ctxtMAT").Text = "MAT-001"
time.sleep(0.5)
session.FindById("wnd[0]/usr/ctxtQTY").Text = "100"
time.sleep(0.5)
session.FindById("wnd[0]/usr/ctxtUNIT").Text = "EA"
time.sleep(0.5)
# Total: 1.5 seconds

# After (fast)
batch_set_fields(session, {
    "wnd[0]/usr/ctxtMAT": "MAT-001",
    "wnd[0]/usr/ctxtQTY": "100",
    "wnd[0]/usr/ctxtUNIT": "EA",
})
# Total: 0.3 seconds
```

### Batch Read Grid Rows

```python
def batch_read_grid(session, grid_id, row_range, columns):
    """
    Read multiple grid rows efficiently.
    
    Args:
        session: SAP session
        grid_id: Grid element ID
        row_range: Tuple (start_row, end_row) or None for all
        columns: List of column names to read
    
    Returns:
        List of dicts (each dict is one row)
    """
    
    grid = session.FindById(grid_id)
    
    if row_range:
        start_row, end_row = row_range
    else:
        start_row = 0
        end_row = grid.RowCount
    
    results = []
    
    for row_idx in range(start_row, end_row):
        row_data = {}
        
        for col_name in columns:
            try:
                value = grid.GetCellValue(row_idx, col_name)
                row_data[col_name] = value
            except:
                row_data[col_name] = None
        
        results.append(row_data)
    
    return results

# Usage - Before (slow)
grid = session.FindById("wnd[0]/usr/cntl.../shellcont/shell")
for row in range(grid.RowCount):
    mat = grid.GetCellValue(row, "MATNR")
    qty = grid.GetCellValue(row, "MENGE")
    time.sleep(0.2)  # Slow!
    # Process...

# After (fast)
data = batch_read_grid(session, "wnd[0]/usr/cntl.../shellcont/shell", None,
                      ["MATNR", "MENGE", "UNIT"])
for row_data in data:
    mat = row_data["MATNR"]
    qty = row_data["MENGE"]
    # Process...
# No per-row waits — much faster for 100+ rows
```

---

## Benchmarking {#benchmarking}

### Measure Performance Before & After

```python
import time

def benchmark_operation(operation_name, operation_func, iterations=1):
    """
    Measure execution time for an operation.
    
    Returns:
        (total_time, avg_time_per_iteration)
    """
    
    print(f"\n→ Benchmarking: {operation_name}")
    
    times = []
    
    for i in range(iterations):
        start = time.time()
        operation_func()
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"  Iteration {i+1}: {elapsed:.2f}s")
    
    total = sum(times)
    average = total / len(times)
    
    print(f"✓ Total: {total:.2f}s, Average: {average:.2f}s/iteration")
    
    return total, average

# Usage - Compare optimizations
def slow_version(session):
    """Original code with fixed 2s waits"""
    for i in range(10):
        session.FindById(f"wnd[0]/usr/ctxtFIELD{i}").Text = f"val{i}"
        time.sleep(2)

def fast_version(session):
    """Optimized with 0.3s smart waits"""
    for i in range(10):
        session.FindById(f"wnd[0]/usr/ctxtFIELD{i}").Text = f"val{i}"
        if i == 9:
            time.sleep(0.3)  # One wait at end

slow_total, _ = benchmark_operation("Slow version", lambda: slow_version(session), 1)
fast_total, _ = benchmark_operation("Fast version", lambda: fast_version(session), 1)

improvement = ((slow_total - fast_total) / slow_total) * 100
print(f"\n✓ Improvement: {improvement:.1f}%")
```

---

## Performance Rules of Thumb

| Scenario | Baseline | Optimized | Speedup |
|----------|----------|-----------|---------|
| 10 field fills + waits | 25s | 8s | **68%** |
| Read 100-row grid | 60s | 15s | **75%** |
| Navigate 5 transactions | 40s | 12s | **70%** |

---

See also:
- [Getting Started — Common Mistakes](../00-foundation/00-getting-started.md#mistakes)
- [Production Error Handling](error-handling-and-recovery.md)
