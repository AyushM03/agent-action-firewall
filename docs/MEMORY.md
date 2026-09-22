# Project Memory

## Current Status
Phase 1 (Setup) complete. Backend and frontend scaffolds both run and are verified end-to-end.

## Completed
- PRD, Architecture, Design, Rules, Tasks, Decisions defined
- Git repo initialized at project root
- Backend: FastAPI app scaffolded per ARCHITECTURE.md folder layout, deps installed in `backend/.venv`, connects to Postgres + Redis, `/health` verified working
- Frontend: Next.js + TypeScript + Tailwind scaffolded, feature folders added, DESIGN.md colors/fonts wired into Tailwind theme, lint/build/dev server all verified working
- `docker-compose.yml` for local Postgres 16 + Redis 7, verified healthy
- `.env.example` written for both apps

## Current Task
Phase 2: Core Data Model (see TASKS.md) — event-sourced schema for agents, action_requests, audit_log, policy_rules.

## Known Issues
- This dev machine has native Postgres/Redis Windows services already on the standard ports (5432/6379), plus an unrelated Docker project on 5433/8000. Project's `docker-compose.yml` uses 5434 (Postgres) and 6380 (Redis) instead — already reflected in `backend/.env.example` and `backend/app/core/config.py` defaults. See CLAUDE.md "Dev-machine port quirks" for the full explanation — don't change these back to the standard ports on this machine.
- No GitHub remote configured yet — repo is git-initialized locally only.

## Next Step
Design the event-sourced schema (agents, action_requests, audit_log, policy_rules) as SQLAlchemy models under `backend/app/models/`, set up Alembic migrations, and seed test agents + policy rules.

Update this file as work progresses — it should always reflect where the project actually is, not where the docs originally planned for it to be.
