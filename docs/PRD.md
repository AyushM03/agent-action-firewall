# Product Requirements Document

## Product
Agent Action Firewall

## Problem
AI agents are increasingly given real-world permissions — sending emails, making payments, calling APIs — but most agent frameworks let them act with almost no guardrails. There's no standard middleware layer that enforces policy, rate-limits actions, requires human approval for risky operations, and keeps an immutable audit trail of what an agent actually did and why.

## Target Users
- Developers building AI agents who need a safety/compliance layer instead of writing one from scratch
- Teams evaluating or demoing "responsible AI agent" architecture (this is also an interview/portfolio narrative — a systems-engineering project, not just a CRUD app)

## Goal
Build a middleware permission-and-audit layer that sits between an AI agent and the real-world actions it wants to take (email, payments, arbitrary API calls), enforcing policy before execution and logging everything immutably.

## Core Features
1. Policy engine (rule-based allow/deny/require-approval per action type)
2. Rate limiting (per-agent, per-action-type, per-time-window)
3. Human-in-the-loop approval workflow for flagged actions
4. Immutable audit log (event-sourced, tamper-evident)
5. Real integrations to prove it works: Gmail API (send email) + a sandbox payment provider (e.g. Stripe test mode)
6. Dashboard to view agent activity, pending approvals, and audit history

## MVP
- Define an agent + register its allowed action types
- Submit an "action request" (e.g. send_email, make_payment) through the firewall
- Policy engine evaluates: auto-allow / auto-deny / needs-approval
- Rate limiter blocks requests exceeding configured thresholds
- Approval queue: a human can approve/reject pending actions from a dashboard
- Every decision (allowed, denied, approved, rejected, executed) is written to an append-only audit log
- Execute the action for real via Gmail API (test inbox) once approved
- Sandbox payment action (Stripe test mode) as a second real integration

## Out of Scope (v1)
- Multi-tenant / org accounts
- Fine-grained RBAC beyond a single "admin approver" role
- Support for arbitrary third-party integrations beyond Gmail + one payment sandbox
- Mobile app
- Billing/monetization

## Success Criteria
A reviewer (or interviewer) should be able to see:
1. An agent request an action
2. The policy engine make a decision with a visible reason
3. A rate-limited or high-risk action get queued for approval
4. A human approve/reject it from a UI
5. The action actually execute (real email sent / test payment processed)
6. A complete, immutable audit trail of the whole sequence

### Remember
PRD = WHAT + WHY
