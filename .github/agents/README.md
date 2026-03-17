# Agent System Quick Reference

**Project**: NiceGUI SAP Automation Framework  
**Agent System Status**: ✅ Initialized and Ready  
**Date**: March 12, 2026

---

## Overview

This project uses a **Multi-Agent System (MAS)** with a Conductor (Orchestrator) and 9 specialized Performer agents. Each agent is a self-contained expert responsible for a specific domain or project phase.

### Agent Roster

| Agent | Role | Phase(s) | File |
|-------|------|----------|------|
| **Orchestrator** | Delegation coordinator & progress tracker | All | [orchestrator.agent.md](orchestrator.agent.md) |
| COM Bridge Architect | Threading, COM lifecycle, queue system | 1, 5 | [com-bridge-architect.agent.md](com-bridge-architect.agent.md) |
| Config Manager | Config schemas, YAML, dependency injection | 0-1 | [config-manager.agent.md](config-manager.agent.md) |
| SAP Scripting Specialist | SAP object model, GuiSession API, grid reading | 1-4 | [sap-scripting-specialist.agent.md](sap-scripting-specialist.agent.md) |
| NiceGUI Frontend Engineer | Web UI, routing, components, async integration | 1-4 | [nicegui-frontend-engineer.agent.md](nicegui-frontend-engineer.agent.md) |
| Screen Inspector Dev | Tree walker, AG-Grid, element inspector | 2 | [screen-inspector-dev.agent.md](screen-inspector-dev.agent.md) |
| Script Runner Dev | VBScript converter, script manager, execution | 3 | [script-runner-dev.agent.md](script-runner-dev.agent.md) |
| Report Engine Dev | YAML report schemas, transaction runner, export | 4 | [report-engine-dev.agent.md](report-engine-dev.agent.md) |
| Error Handling Specialist | Exception translation, retry logic, logging | 5 | [error-handling-specialist.agent.md](error-handling-specialist.agent.md) |
| Testing & QA Engineer | Unit tests, mocking, CI/CD, benchmarks | All | [testing-qa-engineer.agent.md](testing-qa-engineer.agent.md) |

---

## 5-Phase Project Structure

```
Phase 0: Bootstrap (Week 0-1)
  • Project structure, config schema, environment setup
  • Lead: Config Manager

Phase 1: Core Foundation (Week 1-3)
  • COM bridge, SAP session API, NiceGUI bootstrap
  • Leads: COM Bridge Architect, SAP Specialist, Frontend Engineer
  • Blockers for: All subsequent phases

Phase 2: Screen Inspector (Week 3-4)
  • Interactive SAP screen element explorer
  • Lead: Screen Inspector Dev
  • Depends on: Phase 1 complete

Phase 3: Script Runner (Week 5-6)
  • VBScript-to-Python converter, automated script execution
  • Lead: Script Runner Dev
  • Depends on: Phase 1 complete

Phase 4: Report Engine (Week 7-8)
  • YAML-based report definitions, automated data extraction
  • Lead: Report Engine Dev
  • Depends on: Phase 1-2 complete

Phase 5: Polish & Resilience (Week 9+)
  • Error handling, retries, logging, performance optimization
  • Lead: Error Handling Specialist
  • Depends on: Phases 1-4 complete
```

---

## How to Use the Agent System

### For Project Managers / Team Leads

1. **Start with PLAN.md**: Read the current phase status and task breakdown
2. **Check Orchestrator Brief**: Review [orchestrator.agent.md](orchestrator.agent.md) for delegation patterns
3. **Review AGENTS.md**: Understand governance, token budgets, isolation rules

### For Developers (Playing an Agent Role)

1. **Read Your Agent Brief**: Each agent has a dedicated `.agent.md` file with:
   - Core capabilities & expertise area
   - Phase-specific deliverables (code modules, tests, docs)
   - Design constraints & decision-making guidelines
   - Quality standards & acceptance criteria
   - Edge cases & testing strategy

2. **Reference Supporting Docs**:
   - **[REFERENCES.md](../../REFERENCES.md)** ← Start here for all technical documentation
     - SAP GUI Scripting (object model, APIs, security, gotchas)
     - NiceGUI framework reference & patterns
     - Windows COM threading & worker pattern
     - Third-party libraries (PyRFC, openpyxl, Pydantic, etc.)
     - External SAP resources & learning path
   - Individual topic files in `/docs/` (linked from REFERENCES.md)

3. **Check CODEOWNERS**: Confirm module ownership, avoid conflicts

4. **Create Tests First**: Before writing code, create unit tests with >80% coverage target

5. **Update PLAN.md**: After completing a task, update status (🟡 Pending → 🔄 In Progress → ✅ Complete)

### For the Orchestrator (AI Agent Playing Conductor Role)

**Workflow**:

```
1. User requests feature or phase start
   ↓
2. Orchestrator reads PLAN.md to check dependencies & status
   ↓
3. Orchestrator selects Lead Agent(s) for the task
   ↓
4. Orchestrator creates Delegation Brief (see orchestrator.agent.md Section 4)
   ↓
5. Orchestrator hands off to Lead Agent using `agent` tool
   ↓
6. Lead Agent executes, delivers code + tests
   ↓
7. Orchestrator verifies Acceptance Criteria
   ↓
8. Orchestrator updates PLAN.md with completion
   ↓
9. Orchestrator reports status to user
```

---

## Key Files & Their Purposes

### Agent System
- `.github/agents/AGENTS.md` — Governance, token budgets, conflict resolution
- `.github/agents/orchestrator.agent.md` — Conductor instructions
- `.github/agents/*.agent.md` — Individual agent briefs (9 total)

### Project Planning
- `PLAN.md` — Execution tracker, phase tasks, blockers
- `.github/CODEOWNERS` — Module ownership (prevents conflicts)
- `/doc/01-project-plan/` — Architecture & risks

### Code Directories (Post-Phase-1)
- `/sap/` — SAP COM bridge, session API, grid readers
- `/ui/` — NiceGUI application, pages, components
- `/config.py` — Configuration management
- `/main.py` — App entrypoint
- `/tests/` — Unit & integration tests

---

## Architecture Overview

```
┌─────────────────────────────────────────┐
│   NiceGUI Web UI (Frontend)             │
│   ├─ Pages: home, inspector, runner    │
│   └─ Components: tables, forms, modals  │
├─────────────────────────────────────────┤
│   Config Manager (DI, YAML)             │
├─────────────────────────────────────────┤
│   SAP Scripting Layer                   │
│   ├─ Session API (GuiSession wrapper)   │
│   ├─ Grid readers (ALV, tables)         │
│   └─ Inspector (tree walker)            │
├─────────────────────────────────────────┤
│   COM Bridge (Threading Model)          │
│   ├─ Worker thread (SAP COM)            │
│   ├─ Queue (request/response)           │
│   └─ Lifecycle (init, cleanup)          │
├─────────────────────────────────────────┤
│   Windows COM Layer (pywin32)           │
│   └─ SAP GUI Automation API             │
└─────────────────────────────────────────┘
```

---

## Checklist: Getting Started

### Before Phase 1 Starts

- [ ] Read all agent briefs (takes ~2 hours for full understanding)
- [ ] Review PLAN.md and confirm dependencies make sense
- [ ] Set up local development environment (Python 3.10+, SAP GUI Scripting installed)
- [ ] Create `.env` file with SAP credentials (test environment)
- [ ] Run `pip install -r requirements.txt` (after Phase 0 creates it)
- [ ] Confirm team understands agent roles and handoff process

### During Each Phase

- [ ] Check PLAN.md every morning for status updates
- [ ] Lead agent creates and runs unit tests (TDD approach)
- [ ] Testing & QA Engineer validates coverage >80%
- [ ] Orchestrator verifies Acceptance Criteria
- [ ] Update PLAN.md when tasks complete
- [ ] Log blockers immediately (don't wait for end-of-day)

### After Each Phase

- [ ] Conduct brief retrospective (15 min video call or doc)
- [ ] Document lessons learned in phase guide (`/doc/01-project-plan/phase[N]-guide.md`)
- [ ] Update architecture diagram if new patterns emerged
- [ ] Prepare for next phase (brief agents on their phase)

---

## Decision-Making Reference

### Architectural Questions

**Q: Should module X be in `/sap/` or `/ui/`?**  
A: Check CODEOWNERS. If ambiguous, COM Bridge Architect decides for Phase 1, SAP Specialist for Phases 2-4.

**Q: When should I retry an operation?**  
A: Error Handling Specialist decides (Phase 5). For Phase 1-4, implement pessimistic: fail and log.

**Q: How do I handle large data (100k rows)?**  
A: Paginate. SAP Specialist + Report Engine Dev define pagination strategy.

**Q: Should Config Manager use `.env` or `.yaml`?**  
A: Both. `.yaml` for version control, `.env` for secrets (local dev only).

### Testing Questions

**Q: How many tests do I need?**  
A: >80% coverage target. Testing & QA Engineer provides mock fixtures.

**Q: Should I test with real SAP?**  
A: Unit tests: Mock SAP. Integration tests: Real SAP (separate CI job). End-to-end: Real SAP (manual).

**Q: How do I mock pywin32 COM objects?**  
A: See `tests/conftest.py` fixtures (created in Phase 0).

---

## Common Pitfalls & How to Avoid

| Pitfall | Impact | Prevention |
|---------|--------|-----------|
| Skipping Phase 1 | System unstable for all downstream features | Orchestrator gates phases by dependency |
| Circular module dependencies | Build fails, hard to debug | Check CODEOWNERS before each commit |
| COM thread deadlock | App hangs, frustrating for users | Extensive threading tests in Phase 1 |
| Hardcoded credentials | Security risk, blocks deployment | Config Manager enforces .env-only secrets |
| Test coverage <80% | Bugs slip to production | Testing & QA blocks phase completion |
| API breaking changes | Blocks downstream agents | Use versioning, deprecation warnings |

---

## Support & Escalation

### If You're Stuck

1. **Check agent brief**: Your agent's brief should have solved your problem (Section 5-8)
2. **Check reference docs**: `/doc/` has patterns, examples, API references
3. **Ask a specialist**: E.g., "COM Bridge Architect, how do I marshal COM objects across threads?"
4. **Escalate to Orchestrator**: "This task blocks Phase 2, need executive decision"

### If You Discover a Bug in System Design

1. **Document it**: Add comment to PLAN.md blockers section
2. **Propose fix**: Suggest which agent should fix it
3. **Escalate**: Notify Orchestrator within 2 hours
4. **Don't ignore it**: Bugs compound; early fixes save weeks

---

## Success Metrics

**For Individual Agents**:
- Deliver 100% of scope (no unfinished tasks)
- >80% test coverage
- Zero TODO comments (escalate unfinished work)
- Clear handoff notes for dependent agents

**For the System**:
- Phase 1 completion: Week 3 (foundation stable)
- Phase 2-4 completion: Week 8 (all features working)
- Phase 5 completion: Week 12 (production-ready)
- Total test coverage: >80%
- Zero critical bugs (P1-P2) post-Phase-1
- End-user satisfaction: 4/5 or higher

---

## Questions?

**Orchestrator**: Ask via agent delegation mechanism  
**Technical Details**: Review the specific agent brief  
**Architecture**: Check `/doc/01-project-plan/architecture.md`  
**Code Examples**: See agent brief Section 8 (Canonical Examples)

---

**Version**: 1.0  
**Last Updated**: March 12, 2026  
**Maintained By**: Master Agentic Context Engineer
