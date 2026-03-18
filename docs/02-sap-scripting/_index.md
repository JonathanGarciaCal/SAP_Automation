# SAP GUI Scripting Documentation — Master Index

Welcome to the complete SAP GUI automation documentation. Whether you're starting from scratch or optimizing existing scripts, you'll find everything here.

---

## 🚀 Getting Started (New to SAP Scripting?)

Start here if you're beginning SAP GUI automation.

1. **[Getting Started](00-foundation/00-getting-started.md)** ⭐ (15 min read)
   - System requirements & setup
   - Enable SAP scripting step-by-step
   - Your first connection (Hello World!)
   - Common mistakes to avoid

2. **[Object Model & Architecture](00-foundation/01-object-model.md)** (20 min read)
   - SAP GUI hierarchy (Application → Connection → Session)
   - Key objects reference (GuiSession, GuiWindow, GuiGridView)
   - Finding element IDs with Scripting Tracker
   - Common controls (text fields, buttons, grids)

3. **[SAP GUI Launcher & Connection Detection](00-foundation/02-sap-gui-launcher.md)** (15 min read)
   - Open SAP GUI programmatically
   - Find existing sessions by criteria
   - Smart connection logic (detect if running)
   - Session validation & health checks
   - Production-ready `SAPConnectionManager` class

---

## 📚 Practical Guides (Build Real Automations)

Learn workflows and patterns for common automation tasks.

| Guide | Purpose | Time |
|-------|---------|------|
| [Multi-Session Orchestration](02-practical-guides/multi-session-orchestration.md) | Manage multiple SAP systems (PRD, DEV, QAS) simultaneously | 20 min |
| Connection Management *(coming)* | Handle logon dialogs, session pooling, multiple landscapes | 15 min |
| [Grid & Table Operations](02-practical-guides/grid-and-table-operations.md) | Read/modify ALV grids, tree controls, complex data | 30 min |
| Session Monitoring *(coming)* | Display session info, export to CSV, real-time monitoring | 10 min |

---

## ⚡ Production Patterns (Speed & Reliability)

Enterprise-grade patterns for production systems.

| Pattern | Focus | Benefit |
|---------|-------|---------|
| [Performance Optimization](03-production-patterns/performance-optimization.md) | Smart waits, batch operations, benchmarking | **60–70% speedup** |
| Error Handling & Recovery *(coming)* | Connection failures, retry logic, resilience | **Stability** |
| Multi-Window & Dialogs *(coming)* | Safe dialog handling, focus management, popup prevention | **Reliability** |

---

## 🔍 Quick Reference (Lookup Tables & Cheat Sheets)

Look up specific information quickly.

| Reference | Contains |
|-----------|----------|
| [Virtual Key Codes](01-quick-reference/virtual-keys.md) | SendVKey() numbers (F1–F12, Ctrl+Fn combinations) |
| [Security & Tools](01-quick-reference/security-and-tools.md) | RZ11 parameters, authorization, Scripting Tracker setup |
| [VBS → Python Conversion](01-quick-reference/vbs-conversion.md) | Convert SAP-recorded macros to Python (add parens, remove Set) |

---

## 🆘 Troubleshooting (Solve Problems)

When something doesn't work.

| Issue | Solution |
|-------|----------|
| "Could not be found by id" | → See [Getting Started — Common Mistakes](00-foundation/00-getting-started.md#mistakes) |
| Script is too slow | → See [Performance Optimization](03-production-patterns/performance-optimization.md) |
| COM object errors | → See [Getting Started — Verify Installation](00-foundation/00-getting-started.md#verify) |
| Scripting not enabled | → See [Security & Tools — Setup](01-quick-reference/security-and-tools.md) |

---

## 🏗️ Architecture & Design

Understand how our bridge uses SAP GUI scripting:

- **COM Worker Thread** — SAP COM calls isolation ([`sap/bridge.py`](../../sap/bridge.py))
- **Queue Manager** — Async command dispatch ([`sap/queue_manager.py`](../../sap/queue_manager.py))
- **Session Management** — Multi-session orchestration ([`sap/session.py`](../../sap/session.py))
- **Config Schema** — Settings & parameters ([`config.py`](../../config.py))

For full architecture details, see [`doc/06-architecture/patterns.md`](../../doc/06-architecture/patterns.md).

---

## 📖 Learning Path (Recommended Order)

For different experience levels:

### Beginner (New to VB/Python/SAP)
1. [Getting Started](00-foundation/00-getting-started.md) — Setup & first connection
2. [Object Model](00-foundation/01-object-model.md) — Understand SAP GUI structure
3. [Virtual Key Codes](01-quick-reference/virtual-keys.md) — Learn keyboard shortcuts
4. [VBS Conversion](01-quick-reference/vbs-conversion.md) — Convert recorder output

### Intermediate (Some SAP experience)
1. [Integration Guide](02-practical-guides/integration-guide.md) — **START HERE** — Use all components together
2. [SAP GUI Launcher](00-foundation/02-sap-gui-launcher.md) — Programmatic connection
3. [Multi-Session Orchestration](02-practical-guides/multi-session-orchestration.md) — Scale to multiple systems
4. [Performance Optimization](03-production-patterns/performance-optimization.md) — Speed up scripts (60-70% faster)

### Advanced (Building production systems)
1. [Performance Optimization](03-production-patterns/performance-optimization.md) — 60–70% faster
2. Error Handling & Recovery *(coming)* — Production resilience
3. Architecture ([`doc/06-architecture/patterns.md`](../../doc/06-architecture/patterns.md)) — Extend framework

---

## ⚙️ Configuration & Parameters

New SAP parameters in `config.yaml`:

```yaml
sap:
  connection_timeout_sec: 30        # Max seconds to wait for SAP connection
  wait_optimization_enabled: true   # Use SmartWait for 60-70% speedup
  retry_attempts: 3                 # Connection retry attempts with exponential backoff
  retry_backoff_sec: 2              # Initial retry backoff (2s, 4s, 8s, ...)
  sapgui_exe_path: "C:\\Program Files\\SAP\\FrontEnd\\SAP GUI\\saplogon.exe"  # For auto-launch
```

**Override with environment variables:**
```bash
set SAP_CONNECTION_TIMEOUT_SEC=60
set SAP_RETRY_ATTEMPTS=5
set SAP_WAIT_OPTIMIZATION_ENABLED=false
set SAP_LOGON_PATH="C:\\Program Files\\SAP\\FrontEnd\\SAP GUI\\saplogon.exe"
```

---

## 🔧 Utilities & Production Classes

Classes you can import and use:

```python
# Smart connection with auto-launch & retry
from sap.connection_manager import SAPConnectionManager, smart_connect
session = smart_connect("PRD", client="100", auto_launch=True)

# Multi-session orchestration & lookup
from sap.session_manager import SAP_Session_Manager, get_session
sm = SAP_Session_Manager()
session = sm.get_session_by_system_client("PRD", "100")
sm.list_all_sessions_formatted()  # Print all sessions

# Session display & export
from sap.session_display import SessionDisplayManager, display_sessions, export_sessions
display_sessions()  # Print ASCII table
export_sessions("sessions.csv")  # Export to CSV

# Performance optimization (60-70% speedup)
from sap.performance import SmartWait, BatchOperations, Benchmark
SmartWait.until_element_exists(session, "wnd[0]/usr/ctxtMATNR", timeout=10)
BatchOperations.batch_set_fields(session, {"field1": "val1", "field2": "val2"})
Benchmark.run("my_operation", lambda: my_func(), iterations=5)
```

---

## 📖 External Resources

Official SAP documentation and community resources:

- **SAP GUI Scripting API** — Type library reference
- **Scripting Tracker** — https://tracker.stschnell.de/ (element inspector tool)
- **SAP Help Portal** — SAP learning resources
- **Stack Overflow tag**: `sapgui scripting`

---

## 💡 Key Concepts

**Session** — An open SAP window (can have main window + dialogs)

**Connection** — Link to one SAP system (PRD, DEV, QAS = 3 connections)

**Element ID** — Full path to a UI element: `wnd[0]/usr/ctxtMATNR`

**SendVKey** — Simulate keyboard (F8=8, Enter=0, Ctrl+S=11)

**GuiGridView** — ALV grid/table (the main data structure in SAP)

**Busy** — SAP is processing (wait for `!Busy` after navigation)

---

## 📝 Complete Table of Contents

### Foundation
- `00-foundation/00-getting-started.md`
- `00-foundation/01-object-model.md`
- `00-foundation/02-sap-gui-launcher.md`

### Quick Reference
- `01-quick-reference/virtual-keys.md`
- `01-quick-reference/security-and-tools.md`
- `01-quick-reference/vbs-conversion.md`

### Practical Guides
- `02-practical-guides/multi-session-orchestration.md`
- `02-practical-guides/connection-management.md` (coming)
- `02-practical-guides/grid-and-table-operations.md` (coming)
- `02-practical-guides/session-monitoring.md` (coming)

### Production Patterns
- `03-production-patterns/performance-optimization.md`
- `03-production-patterns/error-handling-and-recovery.md` (coming)
- `03-production-patterns/multi-window-and-dialogs.md` (coming)

### Troubleshooting
- `04-troubleshooting/common-issues.md` (coming)

---

## 🎯 Next Steps

Choose your path:

- **Want to use all new components together?** → [Integration Guide](02-practical-guides/integration-guide.md) ⭐ **START HERE**
- **Just getting started?** → [Getting Started](00-foundation/00-getting-started.md)
- **Building multi-system automations?** → [Multi-Session Orchestration](02-practical-guides/multi-session-orchestration.md)
- **Scripts running slow?** → [Performance Optimization](03-production-patterns/performance-optimization.md) (60-70% faster)
- **Looking up syntax?** → [Quick Reference](#quick-reference)

---

## 📞 Help & Support

- **Setup issues?** → Check [Getting Started — Troubleshooting](00-foundation/00-getting-started.md#verify)
- **Can't find elements?** → Download [Scripting Tracker](https://tracker.stschnell.de/) and use Analyzer tab
- **Scripts are slow?** → Measure with [Performance Benchmarking](03-production-patterns/performance-optimization.md#benchmarking)
- **Need examples?** → All guides include 50+ copy-paste ready code snippets

---

**Last Updated:** 2026-03-18 | **Version:** 1.0 | Integrated with SAP_GUI_Python_Complete_Documentation
