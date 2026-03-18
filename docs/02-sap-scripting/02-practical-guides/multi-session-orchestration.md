# Multi-Session Orchestration — Production Patterns

Manage multiple SAP systems and sessions efficiently for advanced automation scenarios.

## Table of Contents

1. [Session Pooling & Management](#pooling)
2. [Multi-System Scenarios](#multisystem)
3. [Session Validation & Health Checks](#validation)
4. [Switching Between Sessions](#switching)
5. [Production-Ready Session Manager](#manager)

---

## Session Pooling & Management {#pooling}

### Maintain a Pool of Ready Sessions

```python
class SessionPool:
    """Maintain a pool of ready sessions"""
    
    def __init__(self):
        self.sessions = {}
        self.max_sessions_per_system = 5
    
    def add_session(self, system, client, session):
        key = f"{system}/{client}"
        if key not in self.sessions:
            self.sessions[key] = []
        self.sessions[key].append(session)
    
    def get_session(self, system, client):
        key = f"{system}/{client}"
        if key in self.sessions and len(self.sessions[key]) > 0:
            return self.sessions[key].pop()
        return None
    
    def return_session(self, system, client, session):
        key = f"{system}/{client}"
        if key not in self.sessions:
            self.sessions[key] = []
        self.sessions[key].append(session)
    
    def size(self):
        return sum(len(s) for s in self.sessions.values())

# Usage
pool = SessionPool()

session = pool.get_session("PRD", "100")
if not session:
    # Get new session (not shown)
    pass

# Use session...

pool.return_session("PRD", "100", session)
```

---

## Multi-System Scenarios {#multisystem}

### Orchestrate Across Systems (PRD, DEV, QAS)

```python
import time

def sync_data_across_systems(config):
    """
    Example: Read master data from PRD, copy to DEV & QAS
    
    config = {
        'prd': {'system': 'PRD', 'client': '100'},
        'dev': {'system': 'DEV', 'client': '100'},
        'qas': {'system': 'QAS', 'client': '100'},
    }
    """
    
    try:
        # Get sessions for all systems
        prd_session = smart_connect(config['prd']['system'], config['prd']['client'])
        dev_session = smart_connect(config['dev']['system'], config['dev']['client'])
        qas_session = smart_connect(config['qas']['system'], config['qas']['client'])
        
        # Read from PRD
        prd_session.StartTransaction("SE16")
        time.sleep(2)
        
        # Extract data (e.g., material list)
        prd_session.FindById("wnd[0]/usr/ctxtTABLE").Text = "MARA"
        prd_session.FindById("wnd[0]").SendVKey(0)  # Execute
        time.sleep(2)
        
        data_prd = read_grid(prd_session, "wnd[0]/usr/cntl.../shellcont/shell")
        
        # Switch to DEV and create records
        dev_session.StartTransaction("MM01")
        time.sleep(2)
        
        for row in data_prd:
            create_material_in_system(dev_session, row)
            time.sleep(1)
        
        # Switch to QAS and create records
        qas_session.StartTransaction("MM01")
        time.sleep(2)
        
        for row in data_prd:
            create_material_in_system(qas_session, row)
            time.sleep(1)
        
        print("✓ Data synced across all systems")
        return True
    
    except Exception as e:
        print(f"✗ Sync failed: {e}")
        return False
```

---

## Session Validation & Health Checks {#validation}

### Before Using a Session

```python
def validate_session(session, expected_system=None, expected_client=None):
    """
    Validate that session is operational.
    
    Return: True if valid, False otherwise
    """
    
    try:
        system = session.Info.SystemName
        client = session.Info.Client
        
        if expected_system and system != expected_system:
            print(f"✗ Wrong system: {system} != {expected_system}")
            return False
        
        if expected_client and client != expected_client:
            print(f"✗ Wrong client: {client} != {expected_client}")
            return False
        
        # Try an operation to see if responsive
        window = session.FindById("wnd[0]")
        if not window:
            return False
        
        print(f"✓ Session valid: {system}/{client}")
        return True
    
    except:
        print("✗ Session is dead")
        return False

# Usage
if validate_session(session, "PRD", "100"):
    # Safe to use
    pass
else:
    # Need new session
    session = smart_connect("PRD", "100")
```

---

## Switching Between Sessions {#switching}

### Switch Focus Between Open Sessions

```python
def get_session_by_index(connection_idx, session_idx):
    """Get specific session"""
    import win32com.client
    
    sap_gui = win32com.client.GetObject("SAPGUI")
    app = sap_gui.GetScriptingEngine
    
    conn = app.Children(connection_idx)
    return conn.Children(session_idx)

def list_and_switch():
    """Demonstrate session switching"""
    
    import win32com.client
    
    sap_gui = win32com.client.GetObject("SAPGUI")
    app = sap_gui.GetScriptingEngine
    
    print("\nOpen Sessions:")
    sessions = []
    
    for ci in range(app.Children.Count):
        conn = app.Children(ci)
        for si in range(conn.Children.Count):
            sess = conn.Children(si)
            tcode = sess.Info.Transaction
            sessions.append((ci, si, sess))
            print(f"  [{len(sessions)-1}] {sess.Info.SystemName}/{sess.Info.Client} - {tcode}")
    
    # Switch to session 0
    if len(sessions) > 0:
        target_ci, target_si, target_sess = sessions[0]
        target_sess.FindById("wnd[0]").SetFocus()
        print(f"✓ Switched to session 0")
```

---

## Production-Ready Session Manager {#manager}

### Complete Session Manager Class

```python
import win32com.client
from typing import Optional, List, Dict
import time

class SAP_Session_Manager:
    """
    Manage multiple SAP sessions across systems.
    
    Features:
    - Session pooling
    - Health checks
    - Retry logic
    - Transaction-specific lookups
    """
    
    def __init__(self):
        self.pools = {}  # Dict[system/client → [sessions]]
    
    def get_session_by_system_client(self, system: str, client: str) -> Optional[object]:
        """
        Find or retrieve session for this system/client combination.
        """
        
        try:
            sap_gui = win32com.client.GetObject("SAPGUI")
            app = sap_gui.GetScriptingEngine
            
            for ci in range(app.Children.Count):
                conn = app.Children(ci)
                for si in range(conn.Children.Count):
                    sess = conn.Children(si)
                    
                    if (sess.Info.SystemName == system and
                        sess.Info.Client == client and
                        sess.Info.Transaction == "SESSION_MANAGER"):
                        
                        return sess
            
            return None
        
        except:
            return None
    
    def get_all_sessions(self) -> List[Dict]:
        """
        Get list of all open sessions with info.
        
        Returns:
            List of dicts with session metadata
        """
        
        sessions = []
        
        try:
            sap_gui = win32com.client.GetObject("SAPGUI")
            app = sap_gui.GetScriptingEngine
            
            for ci in range(app.Children.Count):
                conn = app.Children(ci)
                for si in range(conn.Children.Count):
                    sess = conn.Children(si)
                    
                    sessions.append({
                        'system': sess.Info.SystemName,
                        'client': sess.Info.Client,
                        'user': sess.Info.User,
                        'transaction': sess.Info.Transaction,
                        'language': sess.Info.Language,
                        'conn_idx': ci,
                        'sess_idx': si,
                        'session': sess,
                    })
        
        except:
            pass
        
        return sessions
    
    def validate_session(self, session) -> bool:
        """Check if session is alive"""
        
        try:
            _ = session.Info.SystemName
            return True
        except:
            return False
    
    def close_session(self, system: str, client: str) -> bool:
        """Close session(s) for given system/client"""
        
        try:
            sess = self.get_session_by_system_client(system, client)
            if sess:
                sess.EndTransaction()
                return True
        except:
            pass
        
        return False
    
    def list_all_sessions_formatted(self) -> str:
        """Get pretty-printed session list"""
        
        sessions = self.get_all_sessions()
        
        if not sessions:
            return "No sessions open"
        
        lines = ["\n" + "=" * 80]
        lines.append("OPEN SAP SESSIONS")
        lines.append("=" * 80)
        
        for i, s in enumerate(sessions):
            lines.append(f"\n[{i}] {s['system']}/{s['client']}")
            lines.append(f"    User: {s['user']}")
            lines.append(f"    Transaction: {s['transaction']}")
        
        lines.append("\n" + "=" * 80 + "\n")
        
        return "\n".join(lines)

# Usage
manager = SAP_Session_Manager()

# List all sessions
print(manager.list_all_sessions_formatted())

# Get specific session
session = manager.get_session_by_system_client("PRD", "100")
if session:
    session.StartTransaction("MM01")

# Check if alive
if manager.validate_session(session):
    print("Session is valid")
else:
    print("Session is dead, reconnect")
```

---

See also:
- [Connection Management](connection-management.md) — Opening & closing connections
- [Performance Optimization](../03-production-patterns/performance-optimization.md) — Speed up multi-session work
- [Session Monitoring](session-monitoring.md) — Display & export session info
