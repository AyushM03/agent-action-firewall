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
- [ ] Build approval queue table + API endpoints (list pending, approve, reject)
- [ ] Build approval dashboard UI
- [ ] Ensure every approve/reject writes an audit event
- [ ] Test the full flow: request → needs_approval → human decision → executed or blocked

## Phase 6: Action Executors
- [ ] Gmail executor: OAuth setup, send-email function, wire to "allowed" action outcome
- [ ] Stripe (test mode) executor: create a test payment/charge, wire to "allowed" outcome
- [ ] Both executors write a result event (success/failure) to the audit log

## Phase 7: Dashboard
- [ ] Agent activity view
- [ ] Pending approvals view
- [ ] Full audit log viewer (filter by agent/action/decision)
- [ ] Loading / empty / error states throughout

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
