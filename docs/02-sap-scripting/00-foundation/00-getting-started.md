# Getting Started — SAP GUI Scripting with Python

Welcome to SAP GUI automation! This guide walks you through setup, prerequisites, and your first connection.

## Table of Contents

1. [When to Use SAP GUI Scripting](#when-to-use)
2. [System Requirements](#requirements)
3. [Prerequisites & Setup](#setup)
4. [Enable Scripting in SAP](#enable-scripting)
5. [Install Python Packages](#install-packages)
6. [Your First Connection](#first-connection)
7. [Verify Installation](#verify)
8. [What's Next](#next)

---

## When to Use SAP GUI Scripting {#when-to-use}

### ✅ Good Use Cases
- Automate repetitive GUI workflows
- Test SAP applications end-to-end
- Multi-screen processes (login → data entry → reporting)
- No RFC connectivity available
- Complex authorization flows requiring GUI interaction

### ❌ When NOT to Use
- **You have RFC access** → Use PyRFC instead (50–100× faster)
- **Processing large data volumes** (1,000+ records) → Too slow for GUI
- **Non-Windows systems** → SAP GUI scripting requires Windows COM
- **Real-time integrations** → GUI automation is inherently slow

### Alternatives
| Need | Use Instead |
|------|-------------|
| Fast data extraction | PyRFC (if RFC available) |
| REST/API integration | SAP Analytics Cloud, Fiori elements |
| Batch data load | SAP Data Services, BI tools |
| Web testing | Selenium (for SAP Fiori web interface) |

---

## System Requirements {#requirements}

**Mandatory:**
- Windows OS (Windows 10, 11, Server 2019+)
- SAP GUI for Windows (7.40+, **7.50+ recommended**)
- Python 3.7+ (32-bit or 64-bit matching your SAP GUI architecture)
- Administrator privileges (for initial setup only)

**Recommended:**
- 8 GB RAM minimum
- Stable network connection to SAP system
- Dedicated test user account (not shared with interactive use)

### Check Your SAP GUI Version

1. Open SAP GUI
2. Help → About SAP GUI
3. Note version number (e.g., 7530 = 7.53)

---

## Prerequisites & Setup {#setup}

### Checklist

- [ ] **Step 1:** Enable SAP GUI scripting (see below)
- [ ] **Step 2:** Disable scripting notifications (to prevent hang-ups)
- [ ] **Step 3:** Install Python packages
- [ ] **Step 4:** Run verification script
- [ ] **Step 5:** Test first connection

### Step 1: Enable SAP GUI Scripting

1. Open **SAP GUI**
2. Click **Options** (gear icon) in toolbar
3. Navigate: **Accessibility and Scripting → Scripting**
4. Check ✓ **Enable Scripting** under "User Settings"
5. **Uncheck** ☐ "Notify when scripting window is active" (prevents dialogs interrupting automation)
6. Click **Apply**, then **OK**

**Also disable system notifications (in RZ11 transaction):**
```
Transaction: RZ11
Parameter: sapgui/user_scripting_force_notification
New Value: FALSE
```

### Step 2: Install Python Packages {#install-packages}

```bash
# Install core COM library
pip install pywin32

# Verify pywin32 is registered (may require admin terminal)
python -m pip install pywin32
python Scripts/pywin32_postinstall.py -install
```

If you encounter issues:
```bash
# Python 3.9+ (download wheel manually if needed)
pip install --no-cache-dir pywin32

# Force reinstallation
pip uninstall -y pywin32 && pip install pywin32
python Scripts/pywin32_postinstall.py -install
```

**For 32-bit Python + 64-bit SAP GUI mismatch:**
```bash
# Check your SAP GUI architecture:
# In SAP: Help → About SAP GUI → look for "(32-bit)" or "(64-bit)"

# If mismatch: reinstall matching Python version
# e.g., if SAP is 64-bit, use 64-bit Python 3.11
```

---

## Your First Connection {#first-connection}

### Minimal Connection (Assume SAP Already Open)

```python
import win32com.client

# Get SAP GUI automation object
sap_gui = win32com.client.GetObject("SAPGUI")

# Get scripting engine
app = sap_gui.GetScriptingEngine

# Get first connection and first session
connection = app.Children(0)
session = connection.Children(0)

# Print session info
print(f"System: {session.Info.SystemName}")
print(f"Client: {session.Info.Client}")
print(f"User: {session.Info.User}")
```

**Expected output:**
```
System: PRD
Client: 100
User: TESTUSER
```

### Connection with Error Handling

```python
import win32com.client
from typing import Optional

def connect_to_sap() -> Optional[object]:
    """Connect to first open SAP session with proper error handling"""
    try:
        sap_gui = win32com.client.GetObject("SAPGUI")
        if not sap_gui:
            print("✗ SAP GUI COM object not available")
            return None
        
        app = sap_gui.GetScriptingEngine
        if not app:
            print("✗ Scripting engine not available")
            return None
        
        if app.Children.Count == 0:
            print("✗ No SAP connections open")
            return None
        
        connection = app.Children(0)
        if connection.Children.Count == 0:
            print("✗ No sessions in connection")
            return None
        
        session = connection.Children(0)
        print(f"✓ Connected to {session.Info.SystemName}/{session.Info.Client}")
        return session
    
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return None

# Usage
session = connect_to_sap()
if session:
    print("Ready to automate!")
```

---

## Verify Installation {#verify}

### Quick Verification Script

```python
import sys
import os
import platform

print("=" * 60)
print("SAP GUI SCRIPTING — INSTALLATION VERIFICATION")
print("=" * 60)

# 1. Check Python version
print(f"\n✓ Python {sys.version.split()[0]} ({platform.architecture()[0]})")

# 2. Check pywin32
try:
    import win32com.client
    print("✓ pywin32 available")
except ImportError as e:
    print(f"✗ pywin32 missing: {e}")
    sys.exit(1)

# 3. Check SAP GUI COM object
try:
    sap_gui = win32com.client.GetObject("SAPGUI")
    print("✓ SAP GUI COM object available")
except Exception as e:
    print(f"✗ SAP GUI COM not available:")
    print(f"  - Is SAP GUI running?")
    print(f"  - Is SAP GUI scripting enabled?")
    print(f"  - Did you restart SAP after enabling scripting?")
    print(f"  Error: {e}")
    sys.exit(1)

# 4. Check scripting engine
try:
    app = sap_gui.GetScriptingEngine
    print(f"✓ Scripting engine available ({app.Children.Count} connection(s))")
except Exception as e:
    print(f"✗ Scripting engine error: {e}")
    sys.exit(1)

# 5. Check connections & sessions
try:
    if app.Children.Count > 0:
        connection = app.Children(0)
        session_count = connection.Children.Count
        print(f"✓ First connection has {session_count} session(s)")
        
        if session_count > 0:
            session = connection.Children(0)
            print(f"  • System: {session.Info.SystemName}")
            print(f"  • Client: {session.Info.Client}")
            print(f"  • User: {session.Info.User}")
    else:
        print("⚠ No open connections (open SAP GUI to a system first)")
except Exception as e:
    print(f"✗ Session read error: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All checks passed! Ready to automate.")
print("=" * 60)
```

Run this:
```bash
python verify_installation.py
```

### Troubleshooting Installation

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'win32com'` | Run `pip install pywin32 && python Scripts/pywin32_postinstall.py -install` |
| `AttributeError: GetScriptingEngine` | SAP GUI scripting not enabled; restart SAP after enabling |
| `pywin32_postinstall.py: command not found` | Run from Python Scripts folder: `python -m Scripts.pywin32_postinstall -install` |
| 32-bit vs 64-bit mismatch | Ensure Python and SAP GUI match (both 32-bit or both 64-bit) |
| "Unexpected error: Win32Exception" | Restart terminal as Administrator and reinstall pywin32 |

---

## What's Next {#next}

Congratulations! You've successfully set up SAP GUI scripting.

**Next steps:**

1. **Learn the Object Model** → [SAP GUI Object Model & Architecture](01-object-model.md)
   - Understand the SAP GUI hierarchy: Application → Connection → Session
   - Learn how to find elements using element IDs

2. **Smart SAP Launching** → [SAP GUI Launcher & Connection Detection](02-sap-gui-launcher.md)
   - Open SAP GUI programmatically
   - Auto-detect existing sessions
   - Connect to specific systems

3. **Read Practical Guides** → [Practical Guides](../02-practical-guides/)
   - Multi-session orchestration
   - Grid & table operations
   - Session monitoring

4. **Check Production Patterns** → [Production Patterns](../03-production-patterns/)
   - Performance optimization (60–70% speedup possible)
   - Error handling & recovery
   - Multi-window & dialog management

---

## Common First Mistakes to Avoid

❌ **Mistake 1:** Assume SAP is fast
- SAP GUI needs time to process commands
- Always add reasonable waits (`time.sleep(0.5)` minimum)

❌ **Mistake 2:** Use hard-coded waits everywhere
- Use element existence checks and adaptive waits instead
- See [Performance Optimization](../03-production-patterns/performance-optimization.md)

❌ **Mistake 3:** Hard-code credentials
- Use environment variables or config files
- See `.env` pattern in project root

❌ **Mistake 4:** Test with production data
- Create test users, test materials, test documents
- Start in QAS (quality/test system)

❌ **Mistake 5:** Forget error handling
- Always wrap SAP calls in try-except
- Check element existence before accessing
- Log all operations

---

## Need Help?

- **Element IDs unclear?** → Download [Scripting Tracker](https://www.stschnell.de/) tool
- **Performance slow?** → See [Performance Optimization](../03-production-patterns/performance-optimization.md)
- **Common errors?** → Check [Troubleshooting](../04-troubleshooting/common-issues.md)
- **Design patterns?** → See `.github/memory/CONTEXT.md` for architecture overview
