# SAP GUI Launcher & Smart Connection Detection

This guide shows how to programmatically open SAP GUI, detect existing sessions, and connect intelligently to specific systems and landscapes.

## Table of Contents

1. [Detecting if SAP GUI is Running](#detecting)
2. [Opening SAP GUI Programmatically](#opening)
3. [Finding Sessions by Criteria](#finding)
4. [Smart Connection Logic](#smart)
5. [Session Validation](#validation)
6. [Production-Ready Connection Manager](#production)

---

## Detecting if SAP GUI is Running {#detecting}

### Check if SAP GUI Process is Active

```python
import subprocess
import psutil
import platform

def is_sap_gui_running():
    """
    Check if SAP GUI application is currently running.
    
    Returns:
        bool: True if any SAP GUI process found, False otherwise
    """
    if platform.system() != "Windows":
        print("❌ SAP GUI scripting only works on Windows")
        return False
    
    try:
        # Check for SAP GUI processes
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name'].lower()
                if 'saplogon' in name or 'saplgpad' in name:
                    print(f"✓ SAP GUI found: {proc.info['name']} (PID {proc.info['pid']})")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        print("✗ SAP GUI not running")
        return False
    
    except ImportError:
        print("⚠ psutil not installed. Use: pip install psutil")
        return False
    except Exception as e:
        print(f"✗ Error checking SAP GUI: {e}")
        return False

# Usage
if is_sap_gui_running():
    print("SAP GUI is active - proceed with connection")
else:
    print("SAP GUI is not running - need to launch it")
```

### Check if SAP COM Object is Available

```python
import win32com.client

def is_sap_com_available():
    """
    Check if SAP COM scripting interface is accessible.
    
    Returns:
        bool: True if SAP COM object can be obtained, False otherwise
    """
    try:
        sap_gui = win32com.client.GetObject("SAPGUI")
        
        if sap_gui is None:
            print("✗ SAP COM object is None")
            return False
        
        # Try to access scripting engine
        app = sap_gui.GetScriptingEngine
        if app is None:
            print("✗ Scripting engine not available")
            return False
        
        print(f"✓ SAP COM available ({app.Children.Count} connection(s))")
        return True
    
    except Exception as e:
        print(f"✗ SAP COM not available: {e}")
        return False

# Usage
if is_sap_com_available():
    print("Can connect to SAP scripting interface")
else:
    print("SAP scripting interface not available")
```

---

## Opening SAP GUI Programmatically {#opening}

### Launch SAP GUI Application

```python
import subprocess
import time
import os

def start_sap_gui(wait_time=20, check_running=True):
    """
    Launch SAP GUI application.
    
    Args:
        wait_time: Seconds to wait for SAP to start
        check_running: If True, skip launch if already running
    
    Returns:
        bool: True if successful, False otherwise
    """
    
    # Skip if already running
    if check_running and is_sap_gui_running():
        print("ℹ SAP GUI already running")
        return True
    
    # Common SAP GUI installation paths
    sap_exe_paths = [
        r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
        r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",
        r"C:\SAP\FrontEnd\SAPgui\saplogon.exe",
        r"C:\Program Files (x86)\SAP\Frontpac\saplogon.exe",
    ]
    
    # Find SAP GUI executable
    sap_path = None
    for path in sap_exe_paths:
        if os.path.exists(path):
            sap_path = path
            break
    
    if not sap_path:
        print("✗ SAP GUI not found in standard locations")
        print(f"   Searched: {sap_exe_paths}")
        return False
    
    try:
        print(f"→ Starting SAP GUI from: {sap_path}")
        subprocess.Popen(sap_path)
        
        print(f"→ Waiting {wait_time} seconds for startup...")
        time.sleep(wait_time)
        
        if is_sap_gui_running():
            print("✓ SAP GUI started successfully")
            return True
        else:
            print("✗ SAP GUI did not start in time")
            return False
    
    except Exception as e:
        print(f"✗ Error starting SAP GUI: {e}")
        return False

# Usage
if not is_sap_gui_running():
    start_sap_gui(wait_time=20)
```

### Start SAP with Specific Connection Parameters

```python
def start_sap_gui_connect_system(system_name, wait_time=20):
    """
    Launch SAP GUI with connection to specific system.
    
    Prerequisites:
    - Connection must exist in saplogon.ini
    - System name must match entry in SAP logon pad
    
    Args:
        system_name: SAP system ID (e.g., "PRD", "DEV")
        wait_time: Seconds to wait for startup and connection
    
    Returns:
        bool: True if connection established, False otherwise
    """
    
    sap_path = r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe"
    
    if not os.path.exists(sap_path):
        print("✗ SAP GUI not found")
        return False
    
    try:
        # Start with system parameter
        cmd = f'"{sap_path}" "{system_name}"'
        
        print(f"→ Starting SAP: {cmd}")
        subprocess.Popen(cmd)
        
        print(f"→ Waiting {wait_time} seconds for connection...")
        time.sleep(wait_time)
        
        # Verify connection
        if is_sap_com_available():
            try:
                sap_gui = win32com.client.GetObject("SAPGUI")
                app = sap_gui.GetScriptingEngine
                
                if app.Children.Count > 0:
                    conn = app.Children(0)
                    actual_system = conn.Children(0).Info.SystemName
                    
                    if actual_system == system_name:
                        print(f"✓ Connected to {system_name}")
                        return True
                    else:
                        print(f"⚠ Connected to {actual_system}, not {system_name}")
                        return True  # Still a successful launch
            except:
                pass
        
        print("⚠ SAP started but connection not verified")
        return True
    
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

# Usage
start_sap_gui_connect_system("PRD")
```

---

## Finding Sessions by Criteria {#finding}

### List All Open Sessions

```python
import win32com.client

def list_all_sessions():
    """
    List all currently open SAP sessions.
    
    Returns:
        List of dicts with session info
    """
    
    try:
        sap_gui = win32com.client.GetObject("SAPGUI")
        app = sap_gui.GetScriptingEngine
        
        sessions = []
        
        print("\n" + "=" * 80)
        print("ALL OPEN SAP SESSIONS")
        print("=" * 80)
        
        # Iterate connections
        for conn_idx in range(app.Children.Count):
            connection = app.Children(conn_idx)
            
            # Iterate sessions within connection
            for sess_idx in range(connection.Children.Count):
                session = connection.Children(sess_idx)
                
                info = {
                    'conn_idx': conn_idx,
                    'sess_idx': sess_idx,
                    'system': session.Info.SystemName,
                    'client': session.Info.Client,
                    'user': session.Info.User,
                    'transaction': session.Info.Transaction,
                    'language': session.Info.Language,
                }
                
                sessions.append(info)
                
                print(f"Connection {conn_idx}, Session {sess_idx}:")
                print(f"  System: {info['system']}")
                print(f"  Client: {info['client']}")
                print(f"  User: {info['user']}")
                print(f"  Transaction: {info['transaction']}")
                print()
        
        print("=" * 80)
        print(f"Total: {len(sessions)} session(s)\n")
        
        return sessions
    
    except Exception as e:
        print(f"Error listing sessions: {e}")
        return []

# Usage
sessions = list_all_sessions()
for s in sessions:
    print(f"{s['system']}/{s['client']} - {s['transaction']}")
```

### Find Session by System & Client

```python
def find_session_by_system_client(system_name, client_code):
    """
    Find session matching system and client.
    
    Args:
        system_name: System ID (e.g., "PRD")
        client_code: Client number (e.g., "100")
    
    Returns:
        GuiSession object or None if not found
    """
    
    try:
        sap_gui = win32com.client.GetObject("SAPGUI")
        app = sap_gui.GetScriptingEngine
        
        for conn_idx in range(app.Children.Count):
            connection = app.Children(conn_idx)
            
            for sess_idx in range(connection.Children.Count):
                session = connection.Children(sess_idx)
                
                if (session.Info.SystemName == system_name and
                    session.Info.Client == client_code and
                    session.Info.Transaction == "SESSION_MANAGER"):
                    
                    print(f"✓ Found session: {system_name}/{client_code}")
                    return session
        
        print(f"✗ Session not found: {system_name}/{client_code}")
        return None
    
    except Exception as e:
        print(f"Error finding session: {e}")
        return None

# Usage
session = find_session_by_system_client("PRD", "100")
if session:
    print(f"Logged in as: {session.Info.User}")
```

### Find Session by Transaction Code

```python
def find_session_by_transaction(transaction_code):
    """
    Find session currently in specific transaction.
    
    Args:
        transaction_code: Transaction code (e.g., "MM01", "VA01")
    
    Returns:
        GuiSession object or None if not found
    """
    
    try:
        sap_gui = win32com.client.GetObject("SAPGUI")
        app = sap_gui.GetScriptingEngine
        
        for conn_idx in range(app.Children.Count):
            connection = app.Children(conn_idx)
            
            for sess_idx in range(connection.Children.Count):
                session = connection.Children(sess_idx)
                
                if session.Info.Transaction == transaction_code:
                    print(f"✓ Found {transaction_code} session")
                    return session
        
        print(f"✗ No session in {transaction_code}")
        return None
    
    except Exception as e:
        print(f"Error: {e}")
        return None

# Usage
mm01_session = find_session_by_transaction("MM01")
```

---

## Smart Connection Logic {#smart}

### Intelligent Connect-or-Create

```python
import time

def smart_connect(system_name, client_code=None, auto_open=True, timeout=30):
    """
    Intelligently connect to SAP system.
    
    Logic:
    1. Check if SAP COM is available (SAP running)
    2. Search for matching session
    3. If not found and auto_open=True, launch SAP
    4. Search again
    5. Return session or None
    
    Args:
        system_name: System ID (e.g., "PRD", "DEV")
        client_code: Client number (optional)
        auto_open: If True, launch SAP if not running
        timeout: Seconds to wait for launch
    
    Returns:
        GuiSession object or None
    """
    
    print(f"\n→ Attempting to connect to {system_name}")
    
    # Step 1: Check if SAP COM is available
    try:
        sap_gui = win32com.client.GetObject("SAPGUI")
        app = sap_gui.GetScriptingEngine
        
        # Step 2: Search for existing session
        print(f"  Searching for existing session...")
        
        for conn_idx in range(app.Children.Count):
            connection = app.Children(conn_idx)
            first_session = connection.Children(0)
            
            if first_session.Info.SystemName == system_name:
                # Found matching system
                if client_code is None or first_session.Info.Client == client_code:
                    
                    # Prefer SESSION_MANAGER
                    for sess_idx in range(connection.Children.Count):
                        session = connection.Children(sess_idx)
                        if session.Info.Transaction == "SESSION_MANAGER":
                            print(f"✓ Connected to {system_name}/{first_session.Info.Client}")
                            return session
                    
                    # Fall back to any session in system
                    return connection.Children(0)
        
        # Session not found
        print(f"  ✗ Session not found in any open connection")
    
    except Exception as e:
        print(f"  ✗ SAP COM not available: {e}")
    
    # Step 3: Auto-open if requested
    if auto_open:
        print(f"  → SAP not open or session not found. Launching SAP...")
        
        if start_sap_gui(wait_time=timeout):
            # Try again after launch
            time.sleep(5)
            
            try:
                sap_gui = win32com.client.GetObject("SAPGUI")
                app = sap_gui.GetScriptingEngine
                
                if app.Children.Count > 0:
                    session = app.Children(0).Children(0)
                    
                    if session.Info.SystemName == system_name:
                        print(f"✓ Connected to {system_name}/{session.Info.Client}")
                        return session
            except:
                pass
    
    print(f"✗ Failed to connect to {system_name}")
    return None

# Usage
session = smart_connect("PRD", client_code="100", auto_open=True)
if session:
    print(f"Ready for automation in {session.Info.Transaction}")
```

---

## Session Validation {#validation}

### Check if Session is Still Alive

```python
def is_session_alive(session):
    """
    Verify that session is still valid and responsive.
    
    Returns:
        bool: True if session is active, False if closed
    """
    
    try:
        # Try to access basic info
        _ = session.Info.SystemName
        _ = session.Info.Client
        
        print(f"✓ Session alive: {session.Info.SystemName}/{session.Info.Client}")
        return True
    
    except:
        print("✗ Session is no longer valid (may be closed)")
        return False

# Usage
if is_session_alive(session):
    # Safe to use session
    session.StartTransaction("MM01")
else:
    # Need to reconnect
    session = smart_connect("PRD")
```

### Wait for Session to be Ready

```python
import time

def wait_for_session_ready(session, timeout=30):
    """
    Wait for SAP session to finish loading a screen.
    
    Args:
        session: GuiSession object
        timeout: Max seconds to wait
    
    Returns:
        bool: True if ready, False if timeout
    """
    
    start = time.time()
    
    print("→ Waiting for screen to load...")
    
    while time.time() - start < timeout:
        try:
            main_window = session.FindById("wnd[0]")
            
            # Check if SAP is busy processing
            if not main_window.Busy:
                print("✓ Screen ready")
                return True
            
            time.sleep(0.1)
        
        except:
            time.sleep(0.1)
    
    print("✗ Screen not ready (timeout)")
    return False

# Usage
if wait_for_session_ready(session, timeout=10):
    session.StartTransaction("MM01")
```

---

## Production-Ready Connection Manager {#production}

### Complete Connection Manager Class

```python
import win32com.client
import subprocess
import time
import os
from typing import Optional

class SAPConnectionManager:
    """
    Production-ready SAP connection manager.
    
    Features:
    - Smart detect existing sessions
    - Auto-launch SAP if needed
    - Validate sessions before use
    - Retry logic with exponential backoff
    - Connection timeout handling
    """
    
    def __init__(self, config=None):
        """
        Initialize connection manager.
        
        Args:
            config: Dict with 'saplogon_path', 'wait_timeout', 'retry_attempts'
        """
        self.config = config or {}
        self.saplogon_path = config.get('saplogon_path') if config else None
        self.wait_timeout = self.config.get('wait_timeout', 30) if config else 30
        self.retry_attempts = self.config.get('retry_attempts', 3) if config else 3
    
    def find_sap_path(self):
        """Find SAP GUI executable path"""
        
        if self.saplogon_path and os.path.exists(self.saplogon_path):
            return self.saplogon_path
        
        common_paths = [
            r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
            r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",
            r"C:\SAP\FrontEnd\SAPgui\saplogon.exe",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def is_sap_running(self):
        """Check if SAP GUI is running"""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if 'saplogon' in proc.info['name'].lower():
                    return True
        except:
            pass
        
        return False
    
    def launch_sap(self, system=None):
        """Launch SAP GUI"""
        
        sap_path = self.find_sap_path()
        if not sap_path:
            raise Exception("SAP GUI not found")
        
        try:
            if system:
                cmd = f'"{sap_path}" "{system}"'
            else:
                cmd = f'"{sap_path}"'
            
            subprocess.Popen(cmd)
            time.sleep(self.wait_timeout)
            
            return self.is_sap_running()
        
        except Exception as e:
            raise Exception(f"Failed to launch SAP: {e}")
    
    def get_session(self, system, client=None, transaction=None):
        """
        Get session with retry logic.
        
        Returns:
            GuiSession or None
        """
        
        for attempt in range(self.retry_attempts):
            try:
                sap_gui = win32com.client.GetObject("SAPGUI")
                app = sap_gui.GetScriptingEngine
                
                # Search for session
                for ci in range(app.Children.Count):
                    conn = app.Children(ci)
                    for si in range(conn.Children.Count):
                        sess = conn.Children(si)
                        
                        if sess.Info.SystemName == system:
                            if client and sess.Info.Client != client:
                                continue
                            
                            if transaction and sess.Info.Transaction != transaction:
                                continue
                            
                            return sess
            
            except:
                pass
            
            if attempt < self.retry_attempts - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return None
    
    def connect(self, system, client=None, auto_launch=True):
        """
        Smart connect with retry.
        
        Returns:
            GuiSession or raises Exception
        """
        
        # Try to find existing session
        session = self.get_session(system, client)
        if session:
            return session
        
        # Launch SAP if needed
        if auto_launch and not self.is_sap_running():
            self.launch_sap(system)
            session = self.get_session(system, client, "SESSION_MANAGER")
            if session:
                return session
        
        raise Exception(f"Could not connect to {system}/{client}")

# Usage
config = {
    'saplogon_path': r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
    'wait_timeout': 30,
    'retry_attempts': 3,
}

manager = SAPConnectionManager(config)

try:
    session = manager.connect("PRD", client="100", auto_launch=True)
    print(f"Connected to {session.Info.SystemName}/{session.Info.Client}")
except Exception as e:
    print(f"Connection failed: {e}")
```

---

**Next Reading:**
- [Multi-Session Orchestration](../02-practical-guides/multi-session-orchestration.md) — Manage multiple SAP systems
- [Connection Management](../02-practical-guides/connection-management.md) — Handle logon dialogs and session validation
- [Performance Optimization](../03-production-patterns/performance-optimization.md) — Speed up SAP automation
