# Design System

## Style
Technical, dense-but-readable, "security console" feel — think a mix of a monitoring dashboard and an audit log viewer. Not consumer-app playful.

## Typography
Inter (UI text), JetBrains Mono or similar monospace for JSON payloads, event IDs, and log entries

## Colors
- Primary (actions/links): #6366F1
- Background: #F8FAFC
- Surface/card: #FFFFFF
- Text: #0F172A
- Muted text: #64748B
- Status — Allowed: #16A34A (green)
- Status — Denied: #DC2626 (red)
- Status — Needs Approval: #D97706 (amber)
- Status — Pending: #64748B (gray)

## Components
- Status badges (colored pill) for every action/event state
- Timeline/log view for the audit trail (append-only feel — newest at top, monospace timestamps)
- Approval queue as a card list with Approve/Reject buttons
- Diff-style or JSON-viewer component for showing exactly what an agent requested vs. what was allowed

## Buttons
Primary, Secondary, Destructive (Reject uses Destructive)

## Cards
Border radius: 8px (slightly sharper than a typical consumer app — reinforces the "console" feel)

## UX Requirements
- Mobile responsive (dashboard should at least be usable, not necessarily optimized, on mobile)
- Loading states for async policy/approval actions
- Empty states ("No pending approvals", "No audit events yet")
- Error states (failed action execution must be visibly distinct from "denied by policy")
- Every audit log entry must show: timestamp, agent, action type, decision, reason

### Remember
DESIGN.md = HOW IT SHOULD LOOK AND FEEL
