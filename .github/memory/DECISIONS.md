# Decision Log

> Append-only. Each entry records an architectural or design choice made during the project.
> Format: `### YYYY-MM-DD — {title}` followed by Decision, Rationale, Alternatives rejected, and Agent.
> Never edit or delete existing entries. If a decision is superseded, add a new entry referencing the old one.

---

### 2026-03-12 — Multi-agent system architecture adopted

**Decision**: Use a 10-agent MAS (1 Conductor + 9 Performers) scoped by project phase and code layer.  
**Rationale**: The project spans 5 distinct implementation phases with well-separated concerns (COM threading, SAP scripting, UI, config, testing). Agent specialization keeps context windows focused and prevents cross-concern reasoning errors.  
**Alternatives rejected**: Single monolithic agent (too broad, context overflows); 2-agent split (too coarse, COM/UI concerns bleed together).  
**Agent**: Workspace Architect

### 2026-03-12 — `filesystem` MCP server as sole tool provider

**Decision**: Use `@modelcontextprotocol/server-filesystem` scoped to the project root as the only MCP server.  
**Rationale**: Agents need to read and write project files. No web search or external API access is required during implementation phases. Minimal privilege — no tools beyond what implementation requires.  
**Alternatives rejected**: Adding `brave-search` (no need to search the web during coding); assigning no tools (agents become non-functional).  
**Agent**: Workspace Architect

### 2026-03-12 — Command Queue + Dedicated COM Thread pattern selected

**Decision**: All SAP COM calls go through a dedicated `threading.Thread` with `pythoncom.CoInitialize()`, communicating with the asyncio main thread via `queue.Queue` and `asyncio.Future`.  
**Rationale**: SAP COM objects are apartment-threaded and blocking. Calling them from the asyncio event loop would freeze the NiceGUI UI. This pattern is the standard solution for COM + asyncio interop.  
**Alternatives rejected**: `run.io_bound` with `ThreadPoolExecutor` (COM state not guaranteed across pool threads); calling COM directly from async handlers (causes deadlocks).  
**Agent**: Workspace Architect / COM Bridge Architect (documented from architecture.md)

### 2026-03-14 — Defensive type guards in element tree flattening

**Decision**: Add type guards in `Session.get_element_tree()` and `Session._flatten_element_tree()` to handle both nested dict and flat list structures from COM worker thread.  
**Rationale**: Unit tests mock `queue_manager.call_async()` inconsistently—some return nested dicts (correct), others return flat lists directly (test mock artifacts). Root cause of 25 test failures. Solution provides defensive handling: detect already-flat lists early and bypass flattening; validate all items in `_flatten_element_tree()` are dicts before calling `.get()` to prevent `AttributeError: 'list' object has no attribute 'get'`.  
**Alternatives rejected**: Fixing all test mocks (high effort, test isolation broken); removing type guards (leaves code fragile); raising hard errors without defensiveness (breaks backward compatibility with existing test mocks).  
**Agent**: SAP Scripting Specialist

### 2026-03-14 — Structured Logging with Python Standard Library

**Decision**: Implement structured JSON logging using Python's `logging` module with custom formatters, rotating file handlers, and context enrichment via contextvars.  
**Rationale**: Standard library (no new dependencies); full control over JSON schema; contextvars provides thread-local storage for Python 3.7+; RotatingFileHandler built-in; custom JSONFormatter enables consistent schema across all log entries.  
**Alternatives rejected**: loguru (adds dependency, requires wrapping); structlog (too heavy for single-user Windows tool).  
**Agent**: error-handling-specialist

### 2026-03-14 — JSONFormatter with Automatic Context Enrichment

**Decision**: JSONFormatter extends logging.Formatter, automatically includes contextvars (transaction, field_name, session_id, attempt, step), and drops None values from output.  
**Rationale**: Cleaner JSON output, thread-safe via contextvars, all fields in single log entry, transparent for testing.  
**Alternatives rejected**: Manual context passing (verbose, error-prone); extra dict only (doesn't capture common operational context).  
**Agent**: error-handling-specialist

### 2026-03-14 — UILogHandler for Browser Integration

**Decision**: UILogHandler is a logging.Handler subclass that buffers entries in memory (max 100, configurable), enforces FIFO eviction, and supports optional callback for real-time UI updates.  
**Rationale**: Decoupled from NiceGUI via callback pattern; thread-safe via Lock; browser fetches entries on-demand via get_ui_log_entries(); callback wrapped to prevent handler crashes.  
**Alternatives rejected**: Pushing logs to UI in real-time (requires async queue, complex); storing logs only in file (browser can't view during execution).  
**Agent**: error-handling-specialist

### 2026-03-14 — Rotating File Strategy: 10 MB × 5 Backups

**Decision**: RotatingFileHandler with 10 MB max file size and 5 backups (50 MB total). File naming: sap_bridge.log, sap_bridge.log.1, .log.2, etc.  
**Rationale**: 10 MB handles ~1M log entries (10 bytes avg per entry); 5 backups = 50 MB total covers full app lifecycle; standard RotatingFileHandler naming convention.  
**Alternatives rejected**: Compression (future enhancement); smaller backups (insufficient storage); larger backups (excessive disk use for single tool).  
**Agent**: error-handling-specialist

