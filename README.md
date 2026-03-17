# SAP GUI Automation Bridge

A Windows desktop web application that bridges SAP GUI's COM scripting API to a browser-based NiceGUI frontend. Enables users to automate SAP tasks, inspect screens, convert and run automation scripts, and export reports to CSV/Excel.

**Project**: NiceGUI-based SAP GUI Scripting Framework  
**Status**: Phase 5 - Polish & Resilience (Production Ready)  
**Version**: 1.0.0  
**Last Updated**: March 21, 2026

## Quick Start (3 Steps)

1. **Install dependencies** (first time only):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure** (first time only):
   ```bash
   copy config.example.yaml config.yaml
   notepad config.yaml          # Edit SAP Logon path and client number
   notepad .env                 # Add SAP credentials (SAP_USER, SAP_PASSWORD)
   ```

3. **Run**:
   ```bash
   python main.py
   ```
   Then open browser to: **http://127.0.0.1:8000**

**See also**: [Full installation guide](DEPLOYMENT.md)

---

## Features (Phases 1-5)

### ✅ Phase 1: Core Foundation
- **Home Dashboard**: Connection status, quick actions, recent operations log
- **SAP Connection**: Automated SAP GUI connection via COM, session management
- **Error Handling**: User-friendly error messages, automatic recovery

### ✅ Phase 2: Screen Inspector
- **Screenshots**: Capture SAP screen at any moment with toolbar
- **Element Tree**: Browse SAP screen element hierarchy (text fields, buttons, grids)
- **Quick Extraction**: Copy element properties (SAP IDs, values, coordinates)

### ✅ Phase 3: Script Runner
- **VBScript Upload**: Upload legacy VBScript automation scripts
- **Auto-Conversion**: Convert VBScript to Python (with manual review option)
- **Execution**: Run converted scripts with parameter input
- **Logging**: Full execution logs with timing and errors

### ✅ Phase 4: Report Engine
- **YAML Definitions**: Define SAP reports as YAML files (transaction + fields + filters)
- **Parameter Input**: Web form for report parameters (dates, filters, etc.)
- **Data Export**: Export to CSV (UTF-8) or Excel (.xlsx)
- **Scheduling**: Export saved reports (Phase 4+)

### ✅ Phase 5: Resilience & Polish
- **Advanced Error Handling**: Automatic retry with exponential backoff
- **Audit Logging**: JSON-formatted logs for compliance
- **Performance Monitoring**: Baseline tracking, performance regressions detected
- **UI Refinements**: Improved error display, accessibility, mobile responsiveness

## Architecture

This project uses a **command queue + dedicated COM worker thread** pattern to safely call SAP's apartment-threaded COM objects from a Python asyncio event loop.

### Architecture Overview

```
┌──────────────────────────────────────┐
│  NiceGUI Web Browser (User)          │
│  http://127.0.0.1:8000               │
└────────────────┬─────────────────────┘
                 │ WebSocket
                 ▼
┌──────────────────────────────────────┐
│  Main Thread (asyncio Event Loop)    │
│  ├─ UI handlers (async)              │
│  ├─ NiceGUI router + pages           │
│  └─ Queues AsyncIO futures           │
└────────────────┬─────────────────────┘
                 │ asyncio.Queue
                 │ (Thread-safe Command objects)
                 ▼
┌──────────────────────────────────────┐
│  COM Worker Thread (STA Apartment)   │
│  ├─ pythoncom.CoInitialize()         │
│  ├─ Message loop (loops consuming)   │
│  └─ Executes SAP COM methods         │
└────────────────┬─────────────────────┘
                 │ call_soon_threadsafe()
                 │ (Resolve futures back to main)
                 ▼
┌──────────────────────────────────────┐
│  SAP GUI COM Automation              │
│  (win32com.client.Dispatch)          │
│  GuiApplication → GuiSession → ...   │
└──────────────────────────────────────┘
```

**Key Principle**: Direct SAP COM calls (**never**) run on the asyncio main thread. Instead, commands are queued, executed on a dedicated STA thread, and futures are resolved back via `call_soon_threadsafe()`. This prevents deadlocks.

### Module Overview

| Module | Purpose | Lines | Owner |
|--------|---------|-------|-------|
| [`config.py`](config.py) | Configuration schema + validation (Pydantic) | ~150 | Config Manager |
| [`main.py`](main.py) | App entry point, logging setup, CLI | ~100 | Config Manager |
| [`sap/bridge.py`](sap/bridge.py) | COM worker thread + command queue | ~200 | COM Bridge Architect |
| [`sap/session.py`](sap/session.py) | SAP session API (22+ methods for transactions, grids, etc.) | ~300 | SAP Scripting Specialist |
| [`sap/inspector.py`](sap/inspector.py) | Screenshot capture + element tree walk | ~250 | Screen Inspector Dev |
| [`sap/script_runner.py`](sap/script_runner.py) | VBScript-to-Python conversion + execution | ~300 | Script Runner Dev |
| [`sap/exporter.py`](sap/exporter.py) | Data export to CSV/Excel | ~200 | Report Engine Dev |
| [`sap/error_handler.py`](sap/error_handler.py) | Exception translation, retry logic, resilience | ~200 | Error Handling Specialist |
| [`ui/app.py`](ui/app.py) | NiceGUI app factory + routing | ~200 | NiceGUI Frontend Engineer |
| [`ui/layout.py`](ui/layout.py) | Common layout (header, sidebar) | ~150 | NiceGUI Frontend Engineer |
| [`ui/pages/*.py`](ui/pages/) | Home, Inspector, Script Runner, Reports pages | ~400 | NiceGUI Frontend Engineer |

**Total Implementation**: ~2,450 production lines (Phases 0-5)

---

## Installation & Deployment

### For Development

See [Quick Start](#quick-start-3-steps) above.

### For Production

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for step-by-step production installation, including:
- System requirements verification
- Python environment setup
- SAP configuration (enable scripting)
- First run verification
- Troubleshooting common issues

---

## Security & Best Practices

See **[SECURITY.md](SECURITY.md)** for comprehensive security guidance:
- Threat model and attack vectors
- Credential management (environment variables, secrets)
- Permissions and access control
- Network security
- Input validation and injection prevention
- Audit logging and compliance
- Incident response procedures

**TL;DR**: Credentials in `.env` (never in code), app runs as standard user (not admin), SAP COM calls isolated on dedicated thread, all transactions logged with timestamps.

---

## Known Limitations & Edge Cases

See **[EDGE_CASES.md](EDGE_CASES.md)** for known issues and workarounds:
- Large datasets (grids > 10K rows) timeout → use filters or increase timeout
- Long-running scripts → split into checkpoints or increase timeout
- Session dropout → auto-reconnects, or manual reconnect button
- Unicode characters → fully supported (UTF-8)
- COM thread deadlocks → development issue (not deployment)
- VBScript conversion limitations → some patterns need manual conversion
- SAP scripting disabled → enable via registry key
- Network/firewall issues → VPN or firewall rule
- Performance degradation → check SAP/network load
- Browser compatibility → Chrome/Firefox/Edge ✅, Safari ⚠️, IE11 ❌

---

## Pre-Deployment & Operational Checklists

See **[/doc/10-deployment/PRODUCTION_CHECKLIST.md](doc/10-deployment/PRODUCTION_CHECKLIST.md)** for:
- **Pre-Deployment**: Code quality, security, dependencies, documentation
- **Deployment**: Infrastructure, configuration, SAP setup, first boot
- **Post-Deployment**: Functional verification, logging, performance, security, user acceptance
- **Rollback**: Procedure if deployment fails

---

## Development Guide

### Project Structure

```
.
├── config.py                 # Pydantic configuration schema
├── config.yaml              # Configuration file (create from config.example.yaml)
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (NOT committed, use .env.example)
│
├── sap/                     # SAP COM bridge layer
│   ├── bridge.py            # COM worker thread queue (Phase 1)
│   ├── connection.py        # SAP connection wrapper (Phase 1)
│   ├── session.py           # SAP session API (Phase 1)
│   ├── inspector.py         # Element tree walker (Phase 2)
│   ├── script_runner.py     # Automation engine (Phase 3)
│   ├── exporter.py          # Report export (Phase 4)
│   └── error_handler.py     # Resilience layer (Phase 5)
│
├── ui/                      # NiceGUI frontend
│   ├── app.py               # App factory and routing
│   ├── layout.py            # Common layout components
│   ├── pages/               # Page views
│   │   ├── home.py          # Dashboard
│   │   ├── inspector.py     # Screen inspector (Phase 2)
│   │   ├── script_runner.py # Script runner (Phase 3)
│   │   └── reports.py       # Reports (Phase 4)
│   └── components/          # Reusable components
│       ├── header.py        # Header bar
│       └── sidebar.py       # Navigation sidebar
│
├── models/                  # Data schemas
├── utils/                   # Utility modules
│
├── tests/                   # Test suite
│   ├── conftest.py          # Pytest fixtures
│   ├── test_config.py       # Config tests
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
│
├── doc/                     # Architecture documentation
│   ├── 01-project-plan/
│   ├── 02-sap-scripting/
│   ├── 03-nicegui/
│   ├── 04-win32com/
│   ├── 05-supporting-libs/
│   ├── 06-architecture/
│   └── 07-references/
│
└── .github/
    ├── CODEOWNERS           # Module ownership
    ├── copilot-instructions.md  # Agent/copilot config
    ├── memory/              # Persistent task context
    │   ├── CONTEXT.md
    │   ├── SCRATCHPAD.md
    │   └── DECISIONS.md
    ├── agents/              # Agent briefs
    └── workflows/           # GitHub Actions CI/CD
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage report
pytest tests/ --cov=sap --cov=ui --cov=config --cov-report=html

# Specific test file
pytest tests/test_config.py -v

# Specific test
pytest tests/test_config.py::test_config_loads -v
```

### Code Quality

```bash
# Format code
black .

# Lint
flake8 . --max-line-length=127

# Type check
mypy . --ignore-missing-imports
```

## Architecture Patterns & Design

For detailed architecture documentation, see:

- **[/doc/06-architecture/patterns.md](doc/06-architecture/patterns.md)** — COM threading strategy, command queue pattern, why we use STA threads
- **[/doc/02-sap-scripting/](doc/02-sap-scripting/)** — SAP GUI Scripting object model, VBScript patterns, security setup
- **[/doc/03-nicegui/](doc/03-nicegui/)** — NiceGUI framework reference, async patterns, page routing
- **[/REFERENCES.md](REFERENCES.md)** — Complete index of all technical documentation, learning path, external resources

## Project Roadmap

| Phase | Title | Status | Content |
|-------|-------|--------|---------|
| 0 | Bootstrap | ✅ Complete | Project setup, config schema, CI/CD, agent system |
| 1 | Core Foundation | ✅ Complete | App factory, home dashboard, session API, UI framework |
| 2 | Screen Inspector | ✅ Complete | Screenshot capture, element tree inspection, property extraction |
| 3 | Script Runner | ✅ Complete | VBScript upload, auto-conversion to Python, execution engine |
| 4 | Report Engine | ✅ Complete | YAML report definitions, parameter forms, CSV/Excel export |
| 5 | Resilience & Polish | ✅ Complete | Error handling, audit logging, performance monitoring, documentation |
| 6+ | Advanced Features | 🔄 Future | RFC integration, scheduled reports, dashboard insights, mobile UI |

**See**: [PLAN.md](PLAN.md) for detailed task breakdown and completion timeline.

## Multi-Agent Development System

This project uses a **14-agent development system** for coordinated, role-based implementation:

| Role | Agent | Responsibility | Modules |
|------|-------|-----------------|---------|
| 🎼 Conductor | Orchestrator | Task delegation, phase gates, cross-team coordination | All |
| 📋 Planning | Plan Agent | Pre-implementation discovery, design validation, risk assessment | N/A |
| ⚙️ Configuration | Config Manager | Configuration schema, dependency injection, environment setup | `config.py`, `main.py` |
| 🌉 COM Bridge | COM Bridge Architect | SAP COM threading, worker queue, async/await orchestration | `sap/bridge.py` |
| 📡 SAP API | SAP Scripting Specialist | Session API, transaction execution, grid navigation | `sap/session.py`, `sap/grid_reader.py` |
| 🔍 Inspector | Screen Inspector Dev | Screenshot capture, element tree, property extraction | `sap/inspector.py` |
| 🤖 Automation | Script Runner Dev | VBScript conversion, Python execution, parameter binding | `sap/script_runner.py` |
| 📊 Reports | Report Engine Dev | YAML report definitions, data export, formatting | `sap/exporter.py` |
| 🛡️ Resilience | Error Handling Specialist | Exception translation, retry logic, recovery | `sap/error_handler.py` |
| 🎨 Frontend | NiceGUI Frontend Engineer | Web UI, pages, routing, responsive design | `ui/app.py`, `ui/pages/`, `ui/components/` |
| ✅ QA | Testing & QA Engineer | Test orchestration, coverage tracking, performance baselines | `tests/` |
| 🧪 Unit Tests | Test Batch Unit | Unit test execution (isolated, mocked) | `tests/unit/` |
| 🔗 Integration | Test Batch Integration | Integration test execution (cross-module) | `tests/integration/` |
| ⏱️ Performance | Test Batch Performance | Performance regression detection, benchmarks | `tests/test_performance.py` |

**See**: [AGENTS.md](AGENTS.md) for full agent registry, [`.github/CODEOWNERS`](.github/CODEOWNERS) for module responsibility.

## Contributing

**Note**: This is an internal tool developed by a multi-agent system. For external contributions, fork and file a PR. For internal development, follow the process below.

### Development Workflow

1. **Check PLAN.md** for current sprint tasks — don't duplicate work
2. **Assign yourself** to a task (or ask Orchestrator)
3. **Create feature branch**: `git checkout -b feature/my-feature`
4. **Implement & test** locally (see Code Quality below)
5. **Push & create PR** ← Code owner reviews (see CODEOWNERS)
6. **Merge** once tests pass and code owner approves

### Code Quality

**Pre-commit checks** (run before pushing):

```bash
# Type hints (all public functions required)
mypy sap/ ui/ config.py --ignore-missing-imports

# Style / PEP 8
black sap/ ui/ config.py main.py tests/
flake8 . --max-line-length=127 --ignore=E501,W503

# Tests & coverage (target >80%)
pytest tests/ --cov=sap --cov=ui --cov=config --cov-report=term-missing

# No hard-coded credentials
grep -r "password\|token\|secret" sap/ ui/ config.py | grep -v "os.getenv" | grep -v "#" | grep -v "test_"

# No TODO comments in production code
grep -r "TODO\|FIXME\|HACK" sap/ ui/ config.py --include="*.py" | grep -v "test_"
```

### Coding Standards

- **Type Hints**: Required on all public function signatures. Example:
  ```python
  def execute_transaction(self, tcode: str, params: Dict[str, str]) -> bool:
      """Execute SAP transaction..."""
  ```

- **Docstrings**: Google format on all public classes and methods:
  ```python
  def connect(self) -> bool:
      """Connect to SAP system.
      
      Returns:
          True if successful, False otherwise.
          
      Raises:
          SAPConnectionError: If already connected.
      """
  ```

- **Secrets**: Never hardcode credentials. Always use environment variables:
  ```python
  # ❌ WRONG
  password = "MyPassword123"
  
  # ✅ CORRECT
  password = os.getenv('SAP_PASSWORD')
  ```

- **Comments**: No TODO/FIXME in committed code. Create a task instead.

- **Line Length**: Max 127 characters (not 80 — this is 2026!)

- **Testing**: Every public function must have unit tests. Aim for >80% coverage:
  ```bash
  pytest tests/unit/test_session.py -v
  ```

### Commit Message Format

```
[Module] Brief description (50 chars max)

Longer explanation of the change (if needed).
May span multiple lines.

- List any breaking changes
- Reference any issues: Fixes #123

Example:
[sap] Add Grid.select_multiple() method
  
Implements bulk selection for ALV grids via HotKey(Shift+Space).
Enables fast multi-row operations without looping.

Fixes #045
```

---

## Troubleshooting

**For common deployment issues**, see **[DEPLOYMENT.md](DEPLOYMENT.md#6-troubleshooting)** (Can't connect to SAP, timeout errors, port already in use, bitness mismatch, etc.)

**For edge cases and workarounds**, see **[EDGE_CASES.md](EDGE_CASES.md)** (Large datasets, long-running scripts, session dropout, Unicode, performance degradation, browser compatibility, etc.)

---

## References

### Quick Links

- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Production installation guide
- **[SECURITY.md](SECURITY.md)** — Security audit checklist, threat model
- **[EDGE_CASES.md](EDGE_CASES.md)** — Known limitations, workarounds, troubleshooting
- **[PLAN.md](PLAN.md)** — Project roadmap, task tracker, sprint schedule
- **[AGENTS.md](AGENTS.md)** — Multi-agent system, role assignments, ownership
- **[REFERENCES.md](REFERENCES.md)** — Complete documentation index

### Technical Documentation

- **Architecture**: See [doc/06-architecture/patterns.md](doc/06-architecture/patterns.md) for COM threading, async patterns, design decisions
- **SAP GUI Scripting**: See [doc/02-sap-scripting/](doc/02-sap-scripting/) for object model, methods, security setup, VBScript examples
- **NiceGUI Reference**: See [doc/03-nicegui/reference.md](doc/03-nicegui/reference.md) for framework patterns, UI components
- **Win32COM**: See [doc/04-win32com/reference.md](doc/04-win32com/reference.md) for COM threading, error handling
- **Supporting Libraries**: See [doc/05-supporting-libs/](doc/05-supporting-libs/) for Pydantic, PyYAML, openpyxl, loguru docs
- **Performance Baselines**: See [doc/09-performance/BASELINE.md](doc/09-performance/BASELINE.md) for timing expectations

### External Resources

- **NiceGUI**: https://nicegui.io/ — Web framework documentation
- **Pydantic v2**: https://docs.pydantic.dev/latest/ — Configuration validation
- **pywin32 (win32com)**: https://github.com/mhammond/pywin32 — COM for Python
- **PyYAML**: https://pyyaml.org/ — YAML parsing
- **openpyxl**: https://openpyxl.readthedocs.io/ — Excel generation
- **loguru**: https://loguru.readthedocs.io/ — Structured logging
- **pytest**: https://docs.pytest.org/ — Testing framework
- **SAP Official**: https://help.sap.com/ — SAP GUI scripting (if available)

### Memory & Context

- **Project Context**: See [.github/memory/CONTEXT.md](.github/memory/CONTEXT.md) for tech stack, conventions, architecture constraints
- **Decisions Log**: See [.github/memory/DECISIONS.md](.github/memory/DECISIONS.md) for past architectural decisions
- **Task Scratchpad**: See [.github/memory/SCRATCHPAD.md](.github/memory/SCRATCHPAD.md) (cleared between tasks)

## License

Internal tool — not for distribution. For use by authorized personnel only.

**License Type**: Internal Use Only  
**Copyright**: [Your Organization]  
**Contact**: For licensing questions, contact [IT/Legal]

---

## Support & Contact

### For End Users

- **Installation Issues**: See [DEPLOYMENT.md](DEPLOYMENT.md#6-troubleshooting)
- **Feature Questions**: See [EDGE_CASES.md](EDGE_CASES.md) for known limitations
- **General Support**: Contact your IT Help Desk or [support email]

### For Developers

- **Architecture Questions**: See [doc/06-architecture/patterns.md](doc/06-architecture/patterns.md) or contact COM Bridge Architect
- **SAP Integration Issues**: Contact SAP Scripting Specialist
- **UI/Frontend Issues**: Contact NiceGUI Frontend Engineer
- **Security Concerns**: See [SECURITY.md](SECURITY.md) or contact Error Handling Specialist
- **Test/QA**: Contact Testing & QA Engineer

### For Project Leads

- **Project Status**: See [PLAN.md](PLAN.md)
- **Roadmap/Phases**: See [PLAN.md](PLAN.md) or contact Orchestrator
- **Code Ownership**: See [.github/CODEOWNERS](.github/CODEOWNERS)
- **Agent Assignments**: See [AGENTS.md](AGENTS.md)
- **Decisions/Architecture**: See [.github/memory/DECISIONS.md](.github/memory/DECISIONS.md)

---

**Last Updated**: March 21, 2026  
**Project Status**: ✅ Phase 5 Complete (Production Ready)  
**Maintained By**: Multi-Agent Development Team
