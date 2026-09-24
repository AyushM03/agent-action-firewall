# Project Memory

## Current Status
Phase 4 (Rate Limiting) complete. The decision flow (policy + rate limiter + audit event) works end to end at the service level; there is no HTTP endpoint for it yet.

## Completed
- PRD, Architecture, Design, Rules, Tasks, Decisions defined
- Git repo initialized at project root
- Backend: FastAPI app scaffolded per ARCHITECTURE.md folder layout, deps installed in `backend/.venv`, connects to Postgres + Redis, `/health` verified working
- Frontend: Next.js + TypeScript + Tailwind scaffolded, feature folders added, DESIGN.md colors/fonts wired into Tailwind theme, lint/build/dev server all verified working
- `docker-compose.yml` for local Postgres 16 + Redis 7, verified healthy
- `.env.example` written for both apps
- GitHub remote configured (`origin/main`)
- Phase 2: SQLAlchemy models in `backend/app/models/` (`agents`, `policy_rules`, `action_requests`, `audit_log`), Alembic set up in `backend/migrations/` (async, reads DB URL from app settings). `audit_log` and `action_requests` are insert-only — DB triggers reject UPDATE/DELETE/TRUNCATE. A partial unique index guarantees exactly one decision event (allowed/denied/needs_approval) per request. Seed script: `python -m app.seed`. Tests: `backend/tests/test_audit_log_schema.py`
- Phase 3: policy engine in `backend/app/policy/`. `conditions.py` defines the rule condition format (`{"all": [{"field", "op", "value"}]}`, 10 operators, one function each) and validates it with Pydantic. `engine.py` has the pure `evaluate(agent, action, rules) -> Decision` with default-deny, fail-closed precedence (ADR-005). Seed gained a conditioned rule (payments ≤ $50.00 auto-allowed). Tests: `test_policy_engine.py` (pure) and `test_policy_from_db.py`
- Phase 4: `rate_limits` table (migration `add_rate_limits`), Redis sliding-window limiter in `backend/app/ratelimit/limiter.py` (atomic Lua script), audit write helper `backend/app/events/store.py`, and the decision flow `backend/app/services/firewall.py::submit_action_request` (policy → limiter → action_request + exactly one decision event). See ADR-006. Tests: `test_rate_limiter.py`, `test_firewall_flow.py`

## Current Task
Phase 5: Approval Workflow (see TASKS.md).

## Known Issues
- This dev machine has native Postgres/Redis Windows services already on the standard ports (5432/6379), plus an unrelated Docker project on 5433/8000. Project's `docker-compose.yml` uses 5434 (Postgres) and 6380 (Redis) instead — already reflected in `backend/.env.example` and `backend/app/core/config.py` defaults. See CLAUDE.md "Dev-machine port quirks" for the full explanation — don't change these back to the standard ports on this machine.
- The backend still connects as the `postgres` superuser, which could disable the append-only triggers. A least-privilege app role is part of the Phase 8 security pass.

## Next Step
Expose `submit_action_request` as `POST /actions/request` (first decide how agents authenticate, e.g. per-agent API keys), then build the approval queue: list pending, approve, reject, with an authenticated approver and an audit event for every decision.

Update this file as work progresses — it should always reflect where the project actually is, not where the docs originally planned for it to be.
