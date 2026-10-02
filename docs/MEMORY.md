# Project Memory

## Current Status
Phase 7 (Dashboard) is done as of 2026-10-02: agent activity, pending approvals and a filterable audit log viewer, all behind one approver sign-in. Verified in a real browser against the live backend.

Phase 6 (Action Executors) is code-complete. Allowed requests run immediately, and approved ones run as soon as they're approved, through the Gmail executor (send_email) or the Stripe test-mode executor (make_payment). The outcome is appended as `executed` or `execution_failed`. Payloads are validated per action type before policy runs. Verified live on 2026-10-01: `pytest -m integration` sent a real Gmail message and created a Stripe test PaymentIntent (2 passed).

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
- Phase 5 (ADR-007): agent API keys (`agents.api_key_hash`), `approvers` table with bcrypt passwords, JWT login, and a partial unique index so a request can be approved or rejected only once. `app/services/approvals.py` holds the queue and resolve logic. Routes: `POST /actions/request`, `POST /auth/login`, `GET /auth/me`, `GET /approvals/pending`, `POST /approvals/{id}/approve` and `/reject`. Operator CLI: `python -m app.manage create-approver <username>` and `python -m app.manage issue-agent-key <agent-name>`. Frontend `/approvals` page with sign-in, approval cards, and loading/empty/error states. Tests: `test_api.py`, `test_approvals.py`, `test_security.py` (105 passing)
- Phase 6 (ADR-008): payload schemas in `backend/app/executors/payloads.py`; `gmail.py` and `payments.py` executors; `backend/app/services/execution.py` is the only path to an executor and re-checks the audit log first; a unique index allows one result event per request. `python -m app.manage gmail-auth` prints a Gmail refresh token. Dashboard shows the execution result after approving. Tests: `test_payloads.py`, `test_executors.py`, `test_execution.py`, and opt-in `test_integrations.py` (159 passing)

- Phase 7: read-only `backend/app/services/audit.py` (`list_events` with keyset paging by id, `get_request_history`, `list_agent_activity`, all derived from audit_log). Approver-only routes `GET /audit/events` (filters `agent_id`, `action_type`, repeatable `event_type`, `before`, `limit` ≤ 200; returns `{items, next_before}`), `GET /audit/requests/{id}` and `GET /agents` (counts, pending, last activity, `has_api_key` but never the hash). Frontend: `AppShell` + `lib/approver-session.tsx` give every page one sign-in and a nav; `/` redirects to `/agents`; `/agents` (agent cards + 10 latest events), `/audit` (URL-synced filters, "load older", expandable rows with payload + event history), shared `components/States.tsx`. Tests: `test_audit_api.py` (170 passing)

## Current Task
Phase 8: Testing & Hardening (see TASKS.md).

## Known Issues
- This dev machine has native Postgres/Redis Windows services already on the standard ports (5432/6379), plus an unrelated Docker project on 5433/8000. Project's `docker-compose.yml` uses 5434 (Postgres) and 6380 (Redis) instead — already reflected in `backend/.env.example` and `backend/app/core/config.py` defaults. See CLAUDE.md "Dev-machine port quirks" for the full explanation — don't change these back to the standard ports on this machine.
- The backend still connects as the `postgres` superuser, which could disable the append-only triggers. A least-privilege app role is part of the Phase 8 security pass.

## Next Step
Phase 8: end-to-end tests (risky action → approval → real Gmail send; rate limit → denied), a least-privilege DB role, and the SECURITY.md / ARCHITECTURE.md / RULES.md review.

Update this file as work progresses — it should always reflect where the project actually is, not where the docs originally planned for it to be.
