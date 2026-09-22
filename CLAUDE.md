# CLAUDE.md — Agent Action Firewall

This file is the fast-load summary of the project for Claude Code. Read this first; only open the full files in `docs/` when you need detail this summary doesn't cover. Keep this file in sync whenever a doc changes.

## What this project is
A middleware permission-and-audit layer for AI agents: enforces policy, rate-limits actions, routes risky actions through human approval, and keeps an immutable audit trail — with real integrations (Gmail API, Stripe test mode), not mocks.

## Stack
- Backend: FastAPI (Python), Pydantic models
- Frontend: Next.js + TypeScript + Tailwind
- DB: PostgreSQL, event-sourced (audit log is append-only, source of truth)
- Cache/Rate limiting: Redis (sliding-window/token-bucket per agent_id + action_type)
- Integrations: Gmail API (send-only OAuth scope), Stripe (test mode only)
- Deploy: Vercel (frontend) + container host (backend) + managed Postgres/Redis

## High-level flow
```
Agent → POST /actions/request (FastAPI)
  → Policy Engine (reads rules, pure function, no side effects)
  → Rate Limiter (Redis counters)
  → Decision: ALLOW | DENY | NEEDS_APPROVAL
  → Event written to audit_log (Postgres, append-only)
  → [NEEDS_APPROVAL] Approval Queue → human decision (dashboard) → event written
  → [ALLOW] Action Executor (Gmail/Stripe) → result event written
  → Dashboard reads audit_log + approval_queue
```

## Folder structure (planned)
```
backend/app/{api,policy,ratelimit,executors,events,models,core}
frontend/src/{app,components,features/{approvals,audit-log,agents},services,types,lib}
```

## Hard rules (do not violate)
- Policy evaluation is a pure function — no DB writes, no external calls, no side effects.
- Audit log is append-only, forever — no UPDATE/DELETE, even for admins (enforce at DB level too, not just app convention).
- Executors (Gmail, Stripe) are only called after a decision is ALLOW.
- Every action request produces exactly one audit event, regardless of outcome.
- Frontend never talks to Gmail/Stripe or Postgres/Redis directly — always through the FastAPI backend.
- Gmail OAuth tokens and Stripe keys live only in backend env vars — never sent to/stored on frontend, never logged, never committed.
- Approval endpoint must verify the approver is authenticated — no unauthenticated approvals.
- Business logic stays out of route handlers — routes delegate to `policy/`, `ratelimit/`, `executors/`.
- Changing the audit log schema requires checking `docs/DECISIONS.md` first (see ADR-001).
- Don't modify unrelated files. Small commits, one task per commit, descriptive messages (e.g. `feat(policy): add rate-limit rule evaluator`).

## Architecture decisions already made (see docs/DECISIONS.md for full reasoning)
- ADR-001: Event-sourced append-only audit log in Postgres (not a mutable status table).
- ADR-002: FastAPI backend (not Next.js API routes) — policy/ratelimit/executors need to be a standalone, testable Python service.
- ADR-003: Redis for rate limiting, Postgres for audit trail — separate stores, don't blur them.
- ADR-004: Real Gmail API + Stripe test mode as executors — no mocked/fake actions.
These are locked. If a change seems needed, add a new ADR to DECISIONS.md rather than silently overriding.

## Design system (see docs/DESIGN.md for full detail)
"Security console" feel — technical, dense, not consumer-playful. Inter for UI, JetBrains Mono for JSON/logs/IDs.
Status colors: Allowed #16A34A, Denied #DC2626, Needs Approval #D97706, Pending #64748B. Primary #6366F1. Card radius 8px.
Every audit log entry must show: timestamp, agent, action type, decision, reason. Loading/empty/error states required everywhere.

## Testing expectations (see docs/TEST_PLAN.md)
Every policy rule needs one allow-case test and one deny-case test. Rate limit: N succeeds, N+1 denied, resets after window. Audit log: exactly one event per request, immutability verified at DB layer. Run tests after each task, fix failures before moving on.

## Current status (as of 2026-09-22)
**Phase 1 (Setup) is done.** Backend and frontend both scaffold, install, and run cleanly.
- `backend/`: FastAPI app with the `app/{api,policy,ratelimit,executors,events,models,core}` folder structure from ARCHITECTURE.md. `app/core/config.py` (pydantic-settings), `app/core/db.py` (async SQLAlchemy engine/session), `app/core/redis.py` (async redis client), `app/api/health.py` + `app/main.py` (CORS-enabled FastAPI app). Python venv at `backend/.venv`, deps in `backend/requirements.txt`, verified: imports cleanly, connects to Postgres + Redis, `/health` returns `{"status": "ok"}`.
- `frontend/`: Next.js 16 (App Router, Turbopack) + TypeScript + Tailwind v4, scaffolded via `create-next-app`. Folder structure added: `src/{components,features/{approvals,audit-log,agents},services,types,lib}`. `globals.css` wired with the DESIGN.md status-color palette as Tailwind theme tokens (`bg-surface`, `text-muted`, `text-status-*`, `rounded-card`, etc.), `layout.tsx` uses Inter + JetBrains Mono per DESIGN.md. Verified: lints clean, builds clean, dev server serves `/` with 200.
- `docker-compose.yml` at repo root runs Postgres 16 + Redis 7 for local dev. Verified healthy and reachable from the backend venv.
- `.gitignore` (root, covers backend + defers to `frontend/.gitignore`), `.env.example` in both `backend/` and `frontend/`.
- Git repo initialized at project root (not yet pushed to a remote — no GitHub repo configured yet).

### Dev-machine port quirks (do not "fix" these, they're intentional workarounds)
This machine already runs **native** Postgres (`postgres.exe`, port 5432) and Redis (`redis-server.exe`, port 6379) as Windows services, and has an unrelated Docker project already bound to port 5433/8000. To avoid colliding with any of that, this project's `docker-compose.yml` maps:
- Postgres container → host port **5434** (not 5432)
- Redis container → host port **6380** (not 6379)
`backend/app/core/config.py` defaults and `backend/.env.example` / `backend/.env` already point at 5434/6380 — keep them in sync if you ever change `docker-compose.yml`. Also note: local backend dev server was verified on port **8001**, not 8000, because an unrelated container already holds 8000 on this machine — `frontend/.env.example` still defaults `NEXT_PUBLIC_API_BASE_URL` to `http://localhost:8000` since that's the correct default on a clean machine; only override it locally here if 8000 is still occupied when you run the backend.

## Next step: Phase 2 (Core Data Model)
- Design event-sourced schema: `agents`, `action_requests`, `audit_log`, `policy_rules` (SQLAlchemy models under `backend/app/models/`, Alembic already installed for migrations but not yet initialized).
- Implement `audit_log` as append-only (no UPDATE/DELETE at the DB level — enforce with permissions or triggers, per ADR-001 and RULES.md).
- Seed a couple of test agents and policy rules.
Full phase breakdown lives in `docs/TASKS.md` (9 phases: Setup → Data Model → Policy Engine → Rate Limiting → Approval Workflow → Executors → Dashboard → Testing/Hardening → Deploy).

Update the "Current status" section above as work progresses — this is what future sessions should trust over re-deriving it from scratch. Also update `docs/MEMORY.md` in parallel since it serves the same purpose for human readers of `docs/`.

## Doc index (open only if this summary isn't enough)
- `docs/PRD.md` — what and why, MVP scope, success criteria
- `docs/ARCHITECTURE.md` — full architecture + folder structure
- `docs/DESIGN.md` — full design system
- `docs/RULES.md` — full dev rules
- `docs/DECISIONS.md` — full ADRs
- `docs/MEMORY.md` — live project status (human-facing twin of this file's status section)
- `docs/SECURITY.md` — full security requirements
- `docs/TASKS.md` — full phase-by-phase task breakdown
- `docs/TEST_PLAN.md` — full test plan
