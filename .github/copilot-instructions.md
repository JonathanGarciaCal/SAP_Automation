# Copilot Project Instructions

## Project Context

See `.github/memory/CONTEXT.md` for project identity, tech stack, architecture constraints, and coding conventions. Read this file before starting any task in this workspace.

## Agent System

This project uses a 10-agent multi-agent system (1 Conductor + 9 Performers).  
See `AGENTS.md` at the project root for the full agent registry, tool assignments, and phase-to-agent mapping.  
Agent instruction files are in `.github/agents/`.

## Memory

Agents maintain persistent context in `.github/memory/`:

- `CONTEXT.md` — Static project context (read at session start by all agents)
- `SCRATCHPAD.md` — Active task working memory (managed by Orchestrator only; cleared between tasks)
- `DECISIONS.md` — Append-only architectural decision log (any agent may append; never edit existing entries)

## Key Commands

- **Install**: `pip install -r requirements.txt`
- **Run**: `python main.py` or `run.bat`
- **Test**: `pytest tests/ --cov`

## Documentation & References

For SAP scripting, NiceGUI, Win32COM, and architecture patterns:
- **[REFERENCES.md](../REFERENCES.md)** — Central hub for all technical documentation
  - SAP GUI Scripting (object model, key objects, virtual keys, VBS-to-Python, gotchas)
  - NiceGUI web framework reference
  - Windows COM & threading model
  - Supporting libraries (PyRFC, openpyxl, Pydantic, etc.)
  - Architecture patterns & design decisions
  - External resources & learning path

## Critical Rules (read before writing any code)

1. SAP COM calls must **never** run on the asyncio main thread. Use the COM worker thread queue. See `doc/06-architecture/patterns.md`.
2. No hardcoded credentials anywhere. Use `.env` + `os.getenv()`.
3. Type hints and Google-format docstrings are required on all public functions and classes.
4. Check `PLAN.md` before starting any task to avoid duplicate work.
5. Check `.github/CODEOWNERS` (when created) before modifying any file — each module has an assigned agent owner.
