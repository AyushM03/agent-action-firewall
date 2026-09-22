# Architecture

## Frontend
Next.js + TypeScript (dashboard: agent activity, pending approvals, audit log viewer)

## Styling
Tailwind CSS

## Backend
FastAPI (Python) — this is where the actual firewall logic lives:
- Policy engine
- Rate limiter
- Approval workflow
- Action executors (Gmail, payment sandbox)

## Database
PostgreSQL, modeled as an **event store** — every state change is an appended event, not an in-place update. This is core to the "audit trail" pitch: the log itself is the source of truth.

## Cache / Rate Limiting
Redis — sliding-window or token-bucket counters per (agent_id, action_type)

## Authentication
Simple session/JWT-based auth for the human approver dashboard (this project isn't about multi-user auth, keep it minimal)

## External Integrations
- Gmail API (OAuth, send-only scope) — real action executor #1
- Stripe (test mode) — real action executor #2

## Deployment
Vercel (frontend) + a container host for FastAPI (e.g. Render/Fly.io) + managed Postgres + managed Redis

## High-Level Flow

```
Agent
  ↓
POST /actions/request  (FastAPI)
  ↓
Policy Engine  →  reads policy rules (Postgres)
  ↓
Rate Limiter   →  checks/increments counters (Redis)
  ↓
Decision: ALLOW | DENY | NEEDS_APPROVAL
  ↓
Event written to audit_log (Postgres, append-only)
  ↓
[if NEEDS_APPROVAL] → Approval Queue → Human decision (dashboard) → Event written
  ↓
[if ALLOW] → Action Executor (Gmail / Stripe) → Result event written
  ↓
Dashboard reads audit_log + approval_queue for display
```

## Folder Structure

```
backend/
├── app/
│   ├── api/           # FastAPI routes
│   ├── policy/         # policy engine + rule evaluation
│   ├── ratelimit/       # Redis-backed limiter
│   ├── executors/       # gmail.py, payments.py
│   ├── events/          # event store read/write helpers
│   ├── models/          # Pydantic + DB models
│   └── core/            # config, auth, db session

frontend/
├── src/
│   ├── app/             # Next.js routes
│   ├── components/
│   ├── features/        # approvals/, audit-log/, agents/
│   ├── services/         # API client calls
│   ├── types/
│   └── lib/
```

## Architectural Rules
- All policy decisions must be pure functions of (agent, action, policy rules, recent history) — no side effects during evaluation.
- The audit log is append-only. Nothing is ever updated or deleted from it, even by admins.
- Action executors (Gmail, Stripe) are only called *after* a decision is ALLOW — never before.
- Rate limit counters live in Redis; the audit log (source of truth for "what happened") lives in Postgres.
- Frontend never talks to Gmail/Stripe directly — always through the FastAPI backend.
- Business logic (policy, rate limiting) stays out of API route handlers; routes call into `policy/`, `ratelimit/`, `executors/`.

### Remember
Architecture = HOW
