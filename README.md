# Agent Action Firewall

A middleware permission-and-audit layer for AI agents. It sits between an agent and the real-world actions it wants to take (sending email, making payments, calling APIs), enforces policy and rate limits before execution, routes risky actions through human approval, and keeps an immutable audit trail of everything that happened.

## Why
Most agent frameworks let agents act with almost no guardrails. This project is a standalone systems-engineering piece demonstrating policy enforcement, rate limiting, human-in-the-loop approval, and event-sourced auditing — with real integrations (Gmail API, Stripe test mode), not mocks.

## Stack
- Backend: FastAPI (Python)
- Frontend: Next.js + TypeScript + Tailwind
- Database: PostgreSQL (event-sourced audit log)
- Cache/Rate limiting: Redis
- Integrations: Gmail API, Stripe (test mode)
- Deployment: Vercel (frontend), Render (backend container), Neon (Postgres), Upstash (Redis)

## Docs
See `docs/` for the full project documentation:
- `PRD.md` — what and why
- `ARCHITECTURE.md` — how it's built
- `DESIGN.md` — how it looks
- `RULES.md` — how AI/devs should code on this project
- `TASKS.md` — current task breakdown
- `DECISIONS.md` — permanent architectural decisions
- `MEMORY.md` — current project state
- `TEST_PLAN.md` — what "working" means
- `SECURITY.md` — security requirements
- `DEPLOY.md` — production deployment runbook

## Run locally
```bash
docker compose up -d                      # Postgres (5434) + Redis (6380)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # bin/ on macOS/Linux
cp .env.example .env                      # then fill it in (see comments)
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload
pytest                                    # live Gmail/Stripe tests: pytest -m integration

cd ../frontend
cp .env.example .env.local && npm install && npm run dev
```

## Status
Phases 1–8 (core firewall, approvals, Gmail/Stripe executors, dashboard, hardening) are done. Phase 9 (deploy) is in progress: see `docs/DEPLOY.md` and `docs/MEMORY.md`.
 
