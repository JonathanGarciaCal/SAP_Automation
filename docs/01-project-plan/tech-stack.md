# Technology Stack

## Core Stack

| Layer | Technology | Version | Why This Choice |
|-------|-----------|---------|----------------|
| **Web UI** | NiceGUI | ≥ 3.0 | Pure-Python, backend-first, built on FastAPI + Vue/Quasar. Single process, WebSocket-driven live updates. No JS authoring needed. Ideal for internal tools. |
| **SAP COM** | `win32com.client` (pywin32) | latest | The standard way to access SAP GUI Scripting COM from Python. Used by all known Python-SAP automation projects. |
| **Async** | `asyncio` | stdlib | NiceGUI is built on FastAPI/uvicorn which uses asyncio. All async coordination goes through this. |
| **Threading** | `threading` + `queue` | stdlib | COM objects require a dedicated thread with `CoInitialize`. stdlib queue provides safe cross-thread communication. |
| **Config** | Pydantic v2 + PyYAML | latest | Pydantic gives typed, validated config models. YAML is human-friendly for editing connection settings and report definitions. |
| **Logging** | `logging` (stdlib) or `loguru` | latest | Dual output: rotating log files for audit trail + NiceGUI `ui.log` element for in-browser visibility. |

## Data Export Stack

| Library | Purpose |
|---------|---------|
| `openpyxl` | Generate `.xlsx` Excel files from extracted SAP data |
| `pandas` | Optional — data manipulation, pivoting, and CSV generation for complex extractions |
| `win32clipboard` | Read clipboard contents after Ctrl+A/Ctrl+C in SAP (fast bulk extraction) |

## Optional / Phase 2

| Library | Purpose | When to Add |
|---------|---------|-------------|
| `pyrfc` | Direct RFC calls to SAP (bypass GUI for table reads) | When you need faster bulk data extraction without screen navigation |
| `PyInstaller` | Package as single `.exe` for non-developer distribution | When deploying to users who don't have Python installed |
| `APScheduler` | Cron-like scheduling for recurring report jobs | When users want automated daily/weekly exports |
| `sqlite3` | Lightweight local database for job history and caching | When you need persistent job tracking across app restarts |

## Why NiceGUI Over Alternatives

| Framework | Rejected Because |
|-----------|-----------------|
| Streamlit | Re-runs entire script on every interaction. No fine-grained control. Not suitable for long-lived COM connections. |
| Dash (Plotly) | Heavier, more boilerplate, callback-based reactivity adds complexity for this use case. |
| Flask/Django + JS frontend | Two codebases (Python + JavaScript). Overkill for an internal single-user tool. |
| PyQt / Tkinter | Desktop-only (no browser access). Harder to build modern UI. Threading model conflicts with COM. |
| Gradio | Designed for ML demos, not general-purpose tools. Limited component library. |

NiceGUI wins because it keeps everything in Python, uses WebSockets for live updates (critical for status monitoring), has built-in AG-Grid support (critical for SAP table display), and its asyncio-based architecture aligns naturally with the producer-consumer COM pattern.

## Python Version & Environment

- **Python 3.10+** recommended (for modern type hints and asyncio features)
- **Bitness**: Must match SAP GUI bitness. SAP GUI ≤7.70 is 32-bit only; SAP GUI 8.00+ has 64-bit option.
- **Virtual environment**: Strongly recommended (`python -m venv .venv`)
- **Dependencies file**: `requirements.txt`

```
nicegui>=3.0
pywin32>=306
pydantic>=2.0
pyyaml>=6.0
openpyxl>=3.1
loguru>=0.7
```
