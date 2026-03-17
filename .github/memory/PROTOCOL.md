# Agent Memory Protocol

This file defines the standard memory protocol followed by all performer agents in this project.

## Standard Protocol

- **Reads**: `.github/memory/CONTEXT.md` at session start for project conventions, architecture constraints, and module structure relevant to this agent's scope.
- **Writes**: Appends an entry to `.github/memory/DECISIONS.md` when making a structural design choice (e.g., selecting a pattern, choosing a library, defining an interface contract). Format: `### YYYY-MM-DD — {title}` with Decision, Rationale, Alternatives rejected, Agent.
- **Concurrent write guard**: If the Orchestrator is actively coordinating, report your decision verbally in your response so the Orchestrator can log it to DECISIONS.md. Write directly to DECISIONS.md only when working standalone (without an active Orchestrator session).
- **Does not read `SCRATCHPAD.md`** — that belongs to the Orchestrator.

## Applicability

This protocol applies to all performer agents:
- `com-bridge-architect`
- `sap-scripting-specialist`
- `nicegui-frontend-engineer`
- `screen-inspector-dev`
- `script-runner-dev`
- `report-engine-dev`
- `error-handling-specialist`
- `config-manager`

The `orchestrator` and `testing-qa-engineer` agents have extended or variant protocols defined in their own files.

The `test-batch-*` agents are stateless executors and do not write to memory files.
