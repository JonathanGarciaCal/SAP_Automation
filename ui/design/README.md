# UI Design Directory

This directory contains all design specifications for the SAP GUI automation framework UI. Design specs are the source of truth for implementation in `/ui/pages/`, `/ui/components/`, and `/ui/layout.py`.

## Structure

```
/ui/design/
├── README.md                      # This file
├── _system-design.md              # (Phase 1) Design system: colors, fonts, spacing, component library
├── phase1-app-shell.md            # (Phase 1) App layout, navigation, header/sidebar
├── phase2-inspector.md            # (Phase 2) Inspector page design
├── phase3-script-runner.md        # (Phase 3) Script execution UI design
├── phase4-report-engine.md        # (Phase 4) Report visualization design
├── phase5-resilience.md           # (Phase 5) Error UX, accessibility, polish
├── accessibility.md               # (All phases) WCAG 2.1 Level AA compliance checklist
├── patterns/
│   ├── error-handling-ux.md       # Error message and recovery patterns
│   ├── loading-states.md          # Loading indicators and progress feedback
│   ├── multi-step-forms.md        # Multi-step form workflows
│   ├── confirmation-dialogs.md    # Confirmation and undo patterns
│   ├── data-table-interactions.md # Table, grid, and list interactions
│   └── grid-inspection.md         # AG-Grid patterns for SAP element inspection
└── decisions.log                  # (History) Design rationale and decisions
```

## Design Spec Template

Every design spec follows this structure:

```markdown
# [Feature Name] Design Spec

## Overview
One sentence: what the user can do on this page.

## User Journey
Step-by-step description of user interactions:
1. User enters → UI shows [state]
2. User clicks [element] → [action occurs] → UI shows [feedback]

## Wireframe
ASCII art or Mermaid diagram showing layout, components, and hierarchy.

## Component Breakdown
| Component | Purpose | Type | Behavior |
|---|---|---|---|
| [Name] | [Purpose] | [Type] | [On click/change/focus] |

## Accessibility Requirements
- Keyboard: Tab order is [top to bottom], [key] closes modals
- Screen Reader: [Component] labeled as "[aria label text]"
- Contrast: Text [color ratio], icons [color ratio]
- Focus indicators: [visual description]

## State Transitions
Enabled → Disabled, Loading → Success/Error, etc.

## Error Handling
- If [condition], show: "[Error message]" and [recovery UI]

## Follow-up Actions
- After [user completes task], [next page or state]
```

## Design Ownership

All design specs are created by `ux-designer` agent and reviewed before implementation.

**Design → Implementation Handoff**:
1. UX Designer creates spec at `/ui/design/[feature].md`
2. UX Designer delegates to `nicegui-frontend-engineer`: "Implement per spec at [path]"
3. Engineer implements in `/ui/pages/` or `/ui/components/`
4. Engineer verifies against spec and reports completion
5. UX Designer may provide feedback (iterative refinement)

## Accessibility Standard

All designs must comply with **WCAG 2.1 Level AA**:
- Keyboard navigable (no mouse required)
- Screen reader compatible (semantic labels)
- Color contrast: 4.5:1 for text, 3:1 for graphics
- Focus indicators visible
- No flashing > 3 Hz

See `accessibility.md` for the compliance checklist.

## Design System (To Be Completed)

See `_system-design.md` for:
- Color palette and contrast ratios
- Typography (fonts, sizes, weights)
- Spacing scale (margins, paddings, gaps)
- Component library (buttons, inputs, cards, tables, etc.)
- Theming and dark/light mode support

## Patterns & Reusable Components

See `/patterns/` for common UX solutions:
- Error messages and recovery
- Loading and progress indicators
- Multi-step forms and workflows
- Confirmations and undo
- Data table interactions
- SAP grid inspection patterns

**Principle**: Reuse patterns for consistency. If a new page needs a pattern that doesn't exist, add it to `/patterns/` so future pages can reuse it.

---

*Last updated: 2026-03-17 — managed by `ux-designer` agent*
