# Tasks

## Phase 1: Setup
- [x] Initialize backend (FastAPI) and frontend (Next.js) projects
- [x] Configure TypeScript + Tailwind
- [x] Configure Postgres + Redis (local via Docker Compose is fine to start)
- [x] Configure Git + GitHub repo
- [x] Write .env.example for both apps

## Phase 2: Core Data Model
- [x] Design event-sourced schema: agents, action_requests, audit_log, policy_rules
- [x] Implement audit_log as append-only (no UPDATE/DELETE at the DB level — enforce with permissions or triggers)
- [x] Seed a couple of test agents and policy rules

## Phase 3: Policy Engine
- [x] Define policy rule format (action type → allow/deny/needs_approval + conditions)
- [x] Implement rule evaluator (pure function, no side effects)
- [x] Write tests: at least one allow case and one deny case per rule type

## Phase 4: Rate Limiting
- [x] Implement Redis-backed limiter (per agent, per action type, per time window)
- [x] Wire limiter into the decision flow (limiter runs before/alongside policy engine)
- [x] Test: exceeding the limit produces a DENY with a clear reason

## Phase 5: Approval Workflow
- [x] Build approval queue + API endpoints (list pending, approve, reject) — queue is derived from audit_log, no table (ADR-007)
- [x] Build approval dashboard UI
- [x] Ensure every approve/reject writes an audit event
- [x] Test the full flow: request → needs_approval → human decision → blocked (the "executed" leg lands with the executors in Phase 6)

## Phase 6: Action Executors
- [x] Gmail executor: OAuth setup (`python -m app.manage gmail-auth`), send-email function, wired to "allowed"/"approved" outcomes
- [x] Stripe (test mode) executor: confirmed test PaymentIntent, wired to "allowed"/"approved" outcomes
- [x] Both executors write a result event (executed/execution_failed) to the audit log
- [x] Per-action-type payload validation (ADR-008)
- [x] Live verification with real credentials: `pytest -m integration` passed 2026-10-01 (real Gmail send + Stripe test PaymentIntent)

## Phase 7: Dashboard
- [x] Agent activity view (`/agents`, backed by `GET /agents`)
- [x] Pending approvals view (`/approvals`, now inside the shared dashboard shell)
- [x] Full audit log viewer (`/audit`, backed by `GET /audit/events` + `GET /audit/requests/{id}`; filter by agent/action/event type)
- [x] Loading / empty / error states throughout
- [x] Verified in a real browser against the live backend (desktop + 390px mobile) on 2026-10-02

## Phase 8: Testing & Hardening
- [ ] End-to-end test: agent requests risky action → approval → real Gmail send
- [ ] End-to-end test: agent exceeds rate limit → denied
- [ ] Security pass against SECURITY.md
- [ ] Review against ARCHITECTURE.md and RULES.md

## Phase 9: Deploy
- [ ] Deploy frontend to Vercel
- [ ] Deploy backend + Postgres + Redis
- [ ] Configure production env vars (separate Gmail/Stripe test credentials if needed)
- [ ] Production QA pass
