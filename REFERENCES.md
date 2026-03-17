# Project References & Documentation Index

Quick-access guide to all SAP, NiceGUI, Win32COM, and supporting library documentation.

---

## 📋 Quick Links by Topic

### SAP GUI Scripting
- **[Object Model & Tree Walking](docs/02-sap-scripting/object-model.md)** — Full SAP GUI Scripting object hierarchy
- **[Key Objects Reference](docs/02-sap-scripting/key-objects.md)** — GuiSession, GuiGridView, GuiTableControl, etc.
- **[Virtual Keys (SendVKey) Reference](docs/02-sap-scripting/sendvkey-reference.md)** — Complete key mapping table
- **[VBScript → Python Conversion Guide](docs/02-sap-scripting/vbs-to-python.md)** — Transform SAP VBS to Python
- **[Security, Tools & Gotchas](docs/02-sap-scripting/security-tools-ids-gotchas.md)** — Security parameters, Scripting Tracker, 10 critical gotchas

### NiceGUI Web Framework
- **[NiceGUI Complete Reference](docs/03-nicegui/reference.md)** — Routing, layout, components, background tasks, state management, lifecycle

### Windows COM & Threading
- **[Win32COM Reference](docs/04-win32com/reference.md)** — COM fundamentals, threading model, worker pattern, error handling, bitness concerns

### Supporting Libraries
- **[Supporting Libraries Reference](docs/05-supporting-libs/reference.md)** — PyRFC, openpyxl, Pydantic+YAML, PyInstaller, win32clipboard

### Architecture & Patterns
- **[Architecture Patterns & Bridge Design](docs/06-architecture/patterns.md)** — COM bridge pattern, YAML config schema, error recovery flow

### External Resources & Learning Path
- **[External Links & Learning Path](docs/07-references/links-and-learning-path.md)** — Official SAP docs, community blogs, tools, NiceGUI resources

---

## 🎯 Follow This Learning Path

For new developers or when starting a new phase:

1. **Project Overview** — [docs/01-project-plan/overview.md](docs/01-project-plan/overview.md)
2. **System Architecture** — [docs/01-project-plan/architecture.md](docs/01-project-plan/architecture.md)
3. **Tech Stack & Justifications** — [docs/01-project-plan/tech-stack.md](docs/01-project-plan/tech-stack.md)
4. **SAP Object Model** — [docs/02-sap-scripting/object-model.md](docs/02-sap-scripting/object-model.md)
5. **COM Threading Model** — [docs/04-win32com/reference.md](docs/04-win32com/reference.md)
6. **Bridge Pattern Solution** — [docs/06-architecture/patterns.md](docs/06-architecture/patterns.md)
7. **Development Phases** — [docs/01-project-plan/phases.md](docs/01-project-plan/phases.md)

---

## 📂 Documentation Structure

```
docs/
├── 01-project-plan/              # Project strategy & planning
│   ├── overview.md               # Goals, scope, audience
│   ├── architecture.md           # System architecture & modules
│   ├── tech-stack.md             # Technology choices & rationale
│   ├── phases.md                 # Development phases & milestones
│   └── risks.md                  # Risk matrix & mitigations
│
├── 02-sap-scripting/             # SAP GUI Scripting API reference
│   ├── object-model.md           # Complete object hierarchy
│   ├── key-objects.md            # Core objects & their APIs
│   ├── sendvkey-reference.md     # Virtual key codes
│   ├── vbs-to-python.md          # Language conversion guide
│   └── security-tools-ids-gotchas.md  # Best practices & gotchas
│
├── 03-nicegui/                   # NiceGUI web framework
│   └── reference.md              # Full framework reference
│
├── 04-win32com/                  # Windows COM & threading
│   └── reference.md              # COM fundamentals & patterns
│
├── 05-supporting-libs/           # Third-party libraries
│   └── reference.md              # PyRFC, openpyxl, etc.
│
├── 06-architecture/              # Design patterns & solutions
│   └── patterns.md               # Bridge, threading, config
│
└── 07-references/                # External links & resources
    └── links-and-learning-path.md  # Official docs, blogs, tools
```

---

## 🔍 Common Questions & Where to Find Answers

| Question | Location |
|----------|----------|
| How do I enable SAP GUI Scripting? | [security-tools-ids-gotchas.md](docs/02-sap-scripting/security-tools-ids-gotchas.md) |
| What is the `GuiSession` object? | [key-objects.md](docs/02-sap-scripting/key-objects.md) |
| How do I read data from a SAP grid? | [object-model.md](docs/02-sap-scripting/object-model.md) + [key-objects.md](docs/02-sap-scripting/key-objects.md) |
| How do I press a function key in SAP? | [sendvkey-reference.md](docs/02-sap-scripting/sendvkey-reference.md) |
| How do I convert SAP VBS to Python? | [vbs-to-python.md](docs/02-sap-scripting/vbs-to-python.md) |
| What's the COM threading problem? | [docs/04-win32com/reference.md](docs/04-win32com/reference.md) |
| How is the COM bridge implemented? | [docs/06-architecture/patterns.md](docs/06-architecture/patterns.md) |
| Where do I find external SAP resources? | [links-and-learning-path.md](docs/07-references/links-and-learning-path.md) |

---

## 💡 Key Reminders

- **SAP Scripting is COM-based** and **not thread-safe**. Always use the COM worker thread queue. See [patterns.md](docs/06-architecture/patterns.md).
- **Check the gotchas** in [security-tools-ids-gotchas.md](docs/02-sap-scripting/security-tools-ids-gotchas.md) before debugging initialization errors.
- **Scripting Tracker** is your element inspector. See [links-and-learning-path.md](docs/07-references/links-and-learning-path.md) for download.
- **NiceGUI is async-first**. Background tasks run off the event loop. See [reference.md](docs/03-nicegui/reference.md).

---

Generated: 2026-03-12 | See [AGENTS.md](AGENTS.md) for multi-agent system info | Memory layer: [.github/memory/](./github/memory/)
