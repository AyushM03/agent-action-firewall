# Project Memory

## Current Status
Phase 2 (Core Data Model) complete. Schema, migrations, append-only enforcement and seed data are in place and tested.

## Completed
- PRD, Architecture, Design, Rules, Tasks, Decisions defined
- Git repo initialized at project root
- Backend: FastAPI app scaffolded per ARCHITECTURE.md folder layout, deps installed in `backend/.venv`, connects to Postgres + Redis, `/health` verified working
- Frontend: Next.js + TypeScript + Tailwind scaffolded, feature folders added, DESIGN.md colors/fonts wired into Tailwind theme, lint/build/dev server all verified working
- `docker-compose.yml` for local Postgres 16 + Redis 7, verified healthy
- `.env.example` written for both apps
- GitHub remote configured (`origin/main`)
- Phase 2: SQLAlchemy models in `backend/app/models/` (`agents`, `policy_rules`, `action_requests`, `audit_log`), Alembic set up in `backend/migrations/` (async, reads DB URL from app settings). `audit_log` and `action_requests` are insert-only — DB triggers reject UPDATE/DELETE/TRUNCATE. A partial unique index guarantees exactly one decision event (allowed/denied/needs_approval) per request. Seed script: `python -m app.seed`. Tests: `backend/tests/test_audit_log_schema.py`

## Current Task
Phase 3: Policy Engine (see TASKS.md) — rule format, pure evaluator, allow/deny tests per rule type.

## Known Issues
- This dev machine has native Postgres/Redis Windows services already on the standard ports (5432/6379), plus an unrelated Docker project on 5433/8000. Project's `docker-compose.yml` uses 5434 (Postgres) and 6380 (Redis) instead — already reflected in `backend/.env.example` and `backend/app/core/config.py` defaults. See CLAUDE.md "Dev-machine port quirks" for the full explanation — don't change these back to the standard ports on this machine.
- The backend still connects as the `postgres` superuser, which could disable the append-only triggers. A least-privilege app role is part of the Phase 8 security pass.

## Next Step
Define the `policy_rules.conditions` format and implement the pure rule evaluator in `backend/app/policy/` (highest-priority matching active rule wins; agent-specific rules over global ones), with an allow-case and a deny-case test per rule type.

Update this file as work progresses — it should always reflect where the project actually is, not where the docs originally planned for it to be.
