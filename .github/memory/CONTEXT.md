# Project Context

NiceGUI SAP Automation Framework — a Windows desktop web application that bridges SAP GUI's COM scripting API to a browser-based NiceGUI frontend. Single-user internal tool. Not distributed.

## Tech Stack

| Layer | Technology |
|---|---|
| Web UI | NiceGUI ≥ 3.0 (FastAPI + Vue/Quasar, asyncio, WebSocket-driven) |
| SAP COM | `win32com.client` (pywin32) — apartment-threaded, blocking |
| Async | `asyncio` (stdlib) — NiceGUI's event loop on the main thread |
| Threading | `threading` + `queue` (stdlib) — COM requires a dedicated STA thread |
| Config | Pydantic v2 + PyYAML |
| Logging | `loguru` — rotating files + `ui.log` element in browser |
| Data export | `openpyxl`, optionally `pandas` |

## Key Commands

- **Install**: `pip install -r requirements.txt` (activate `.venv` first)
- **Run**: `python main.py` or `run.bat`
- **Test**: `pytest tests/ --cov` (target: >80% coverage per module)
- **Lint**: PEP 8 + type hints required; Google-format docstrings

## Core Architecture Constraint

SAP COM objects are apartment-threaded and blocking. They **must never** be called from the asyncio event loop (main thread). The architecture uses a **Command Queue + Dedicated COM Thread** pattern:

- Main thread: asyncio / NiceGUI UI handlers. Creates `asyncio.Future`, puts `Command` on queue, `await`s the future.
- COM worker thread: calls `pythoncom.CoInitialize()`, runs a `while True` loop consuming the queue, resolves futures via `loop.call_soon_threadsafe()`.
- Command objects carry only method names and primitive arguments — never COM object references.

Violating this constraint causes deadlocks or crashes. Every agent must respect it.

## Python Environment

- Python 3.10+ (bitness must match SAP GUI install — usually 32-bit for SAP GUI ≤ 7.70)
- Virtual environment: `.venv/` (not committed)
- Credentials: never hardcoded. Read from `.env` via environment variables (`SAP_PASSWORD`, etc.)

## Coding Conventions

- Type hints on all function signatures
- Google-format docstrings on all public classes and methods
- No TODO comments in committed code — complete or create a tracked task
- Feature branches only — never commit directly to `main`
- Module boundaries enforced by `.github/CODEOWNERS`

## Technical Documentation

All agents should consult these references for domain-specific guidance:

- **[REFERENCES.md](../../REFERENCES.md)** — Complete index of project documentation
  - SAP GUI Scripting (object model, APIs, security, gotchas)
  - NiceGUI framework 
  - Windows COM threading patterns
  - Third-party library references
  - External SAP resources and learning path

## Project Status (as of 2026-03-12)

Phase 0 Bootstrap is in progress. Agent briefs are complete. Config schema, CODEOWNERS, and CI/CD are pending. See `PLAN.md` for full task tracker.

## Key Reference Docs

- Architecture patterns: `doc/06-architecture/patterns.md`
- SAP object model: `doc/02-sap-scripting/object-model.md`
- NiceGUI reference: `doc/03-nicegui/reference.md`
- Phase plan & task tracker: `PLAN.md`
- Agent governance: `AGENTS.md`
