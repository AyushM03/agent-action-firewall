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
- Deployment: Vercel (frontend) + container host (backend)

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

## Status
Planning complete, implementation not started. See `docs/MEMORY.md` for the live status.
"# agent-action-firewall" 
