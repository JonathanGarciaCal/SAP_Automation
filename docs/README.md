# SAP GUI Bridge — Documentation Repository

> A NiceGUI web application that bridges a browser-based UI to a running SAP GUI session via `win32com` / SAP GUI Scripting COM on Windows.

## Repository Structure

```
sap-gui-bridge-docs/
│
├── README.md                          ← You are here
│
├── 01-project-plan/
│   ├── overview.md                    # Project summary, goals, scope
│   ├── architecture.md                # System architecture & module decomposition
│   ├── tech-stack.md                  # Technology choices & justifications
│   ├── phases.md                      # Development phases & milestones
│   └── risks.md                       # Risk matrix & mitigations
│
├── 02-sap-scripting/
│   ├── object-model.md                # Full SAP GUI Scripting object hierarchy & tree walking
│   ├── key-objects.md                 # GuiSession, GuiGridView, GuiTableControl, GuiModalWindow, GuiStatusbar
│   ├── sendvkey-reference.md          # Complete virtual key mapping table
│   ├── vbs-to-python.md              # VBScript → Python conversion guide with automated converter
│   └── security-tools-ids-gotchas.md  # Security params, Scripting Tracker, element ID patterns, 10 gotchas
│
├── 03-nicegui/
│   └── reference.md                   # Full reference: routing, layout, components, background tasks, state, lifecycle
│
├── 04-win32com/
│   └── reference.md                   # COM fundamentals, threading model, worker pattern, error handling, bitness
│
├── 05-supporting-libs/
│   ├── reference.md                   # PyRFC, Pydantic+YAML, PyInstaller, win32clipboard
│   └── openpyxl.md                    # Excel read/write/modify; AI agent patterns for spreadsheet processing
│
├── 06-architecture/
│   └── patterns.md                    # COM bridge pattern, config schema (YAML), error recovery flow
│
└── 07-references/
    └── links-and-learning-path.md     # All URLs, SAP OSS notes, 10-day learning path
```

## Quick Start

If you're new to this project, read the documents in this order:

1. `01-project-plan/overview.md` — What we're building and why
2. `01-project-plan/architecture.md` — How the pieces fit together
3. `02-sap-scripting/object-model.md` — The SAP GUI Scripting API tree
4. `04-win32com/threading-model.md` — The most critical technical challenge
5. `06-architecture/com-bridge-pattern.md` — The solution to that challenge
6. `03-nicegui/background-tasks.md` — How the UI talks to the COM thread
7. `02-sap-scripting/vbs-to-python.md` — Converting SAP macros to Python

## Prerequisites Checklist

Before writing any code, validate these:

- [ ] SAP GUI Scripting enabled server-side (`sapgui/user_scripting = TRUE` via RZ11)
- [ ] Client-side notification pop-ups suppressed
- [ ] Python bitness matches SAP GUI bitness (test `GetObject("SAPGUI")`)
- [ ] `pywin32` installed and working
- [ ] NiceGUI installed (`pip install nicegui`)
