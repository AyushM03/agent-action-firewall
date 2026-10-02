# Architecture Decisions

## ADR-001
**Decision:** Use an event-sourced audit log (append-only) in PostgreSQL rather than a mutable "status" table.
**Reason:** The whole point of the project is a tamper-evident record of agent actions. An append-only log is the honest way to prove that; a mutable table would undercut the core pitch.

## ADR-002
**Decision:** Use FastAPI for the backend rather than doing everything in Next.js API routes.
**Reason:** The policy engine, rate limiter, and executors are the real substance of this project. A separate typed Python service makes that logic easier to test in isolation and easier to explain in an interview as a standalone system.

## ADR-003
**Decision:** Use Redis for rate limiting, Postgres for the audit trail — not one store for both.
**Reason:** Rate-limit counters are ephemeral and need fast increment/expire semantics; the audit trail needs to be permanent and queryable. Mixing them into one store would blur that distinction.

## ADR-004
**Decision:** Use real Gmail API + Stripe test mode as the two action executors, instead of mocked/fake actions.
**Reason:** A firewall that only ever "pretends" to act doesn't prove anything. Real (but safe/sandboxed) integrations make the demo credible.

## ADR-005
**Decision:** The policy engine is default-deny and fails closed. Precedence: inactive agent or unregistered action type → DENY; otherwise the first matching active rule wins, ordered by higher priority, then agent-specific over global, then most restrictive effect (deny > needs_approval > allow) on an exact tie. No matching rule → DENY. A rule whose conditions can't be evaluated against the payload (missing field, wrong type) → DENY with code `policy_error`, rather than skipping the rule.
**Reason:** A firewall must never let an action through because of an omission or ambiguity. Skipping an unevaluable deny rule would silently turn it into an allow; resolving ties toward the safer effect keeps misconfigurations from widening access.

## ADR-006
**Decision:** Rate limits are configured in a Postgres `rate_limits` table (agent_id NULL = default for all agents; if an agent has any limits of its own for an action type, they replace the defaults; several windows can apply at once). Counters are a Redis sliding-window log, checked and updated atomically in one Lua script. The policy engine runs first, and only requests it doesn't deny are counted. A limit breach turns the decision into DENY with code `rate_limited`. If Redis is unreachable, the request is denied with code `rate_limiter_unavailable`.
**Reason:** Limits are configuration that should be inspectable next to policy rules, while counters are ephemeral (ADR-003). A sliding window avoids the burst-at-boundary problem of fixed windows, and the Lua script keeps concurrent requests from overshooting. Counting only non-denied requests means the budget measures actions that could actually happen. Failing closed when Redis is down follows ADR-005.

## ADR-007
**Decision:** Agents authenticate to `POST /actions/request` with a per-agent API key in the `X-API-Key` header. Keys are random (`aaf_` + 32 bytes), shown once when issued (`python -m app.manage issue-agent-key`), and stored only as a SHA-256 hash in `agents.api_key_hash`. The agent's identity comes from the key alone; the request body never names an agent. Human approvers are rows in an `approvers` table (bcrypt password hash) and log in via `POST /auth/login` for a short-lived HS256 JWT (`role: approver`), which is re-checked against the table on every call so deactivation is immediate. The approval queue has no table of its own: a request is pending when its decision event is `needs_approval` and it has no `approved`/`rejected` event. A second partial unique index on `audit_log` (`uq_audit_log_one_resolution_per_request`) allows at most one approved/rejected event per request.
**Reason:** An agent ID in the body would let anyone who learns a UUID act as that agent. Keys are high-entropy, so a fast hash is enough and allows an indexed lookup; passwords are low-entropy, so they get bcrypt. Deriving the queue from events keeps ADR-001 intact (no status column), and enforcing "resolved once" in the database means two approvers clicking at the same time can't both win, which an application-level check alone wouldn't prevent.

## ADR-008
**Decision:** Actions execute inline, within the HTTP call that authorizes them: `POST /actions/request` runs the executor right after an `allowed` decision, and `POST /approvals/{id}/approve` runs it right after the `approved` event is committed. `app/services/execution.py::execute_request` is the only caller of executors, and it re-reads the request's events itself, so it only runs an action with an `allowed` or `approved` event, and never one that already has a result. A third partial unique index (`uq_audit_log_one_result_per_request`) allows at most one `executed`/`execution_failed` event per request. A failure is recorded, never retried automatically. Before policy runs, payloads are validated against a strict per-action-type schema (`app/executors/payloads.py`, unknown fields rejected). An invalid payload or unknown action type is still recorded, as DENIED (`invalid_payload` / `unknown_action_type`). The Stripe executor refuses any key that isn't `sk_test_`/`rk_test_`, and it uses `aaf-<request_id>` as the idempotency key.
**Reason:** Inline execution means the agent or approver sees the real outcome in the response, and it needs no worker or queue infrastructure for an MVP. The cost is a small crash window: if the process dies after the external call but before the result event is written, there's no result event. Stripe's idempotency key makes a manual retry safe for payments; Gmail has no equivalent, so no retry is automatic. Checking authorization inside the executor path, and not in the routes, keeps "executors only run after ALLOW" true no matter who calls it. Validating payloads before policy means conditions like `amount <= 5000` only ever see well-typed data. Recording invalid requests keeps "every request produces exactly one decision event" true.

## ADR-009
**Decision:** The backend connects to Postgres as a login in the `aaf_app` group role, never as a superuser or the table owner. `aaf_app` has SELECT/INSERT on `audit_log` and `action_requests`, SELECT/INSERT/UPDATE on the config tables, and no DELETE, TRUNCATE or DDL anywhere. Alembic and the DB-layer tests use a separate owner login (`MIGRATION_DATABASE_URL`). The login's password is set by the operator, never in a migration. At startup, outside `ENVIRONMENT=development`, the app refuses to run if its DB login can act as the owner of `audit_log` or is a superuser, or if `JWT_SECRET` is the placeholder or under 32 characters; in development those are logged as warnings. Approver login is throttled (10 attempts per 5 minutes per username and per client address, Redis down → refuse).
**Reason:** The append-only triggers (ADR-001) only protect the log from logins that can't turn them off, and a superuser or owner can. With the app role, rewriting history needs credentials the running service doesn't have. Checking at startup turns a silent misconfiguration into a refusal to start, the same fail-closed stance as ADR-005. Approvers are the human gate on risky actions, so their passwords can't be open to unlimited guessing.

This file prevents the AI coding tool from silently changing these decisions later — if a change is needed, add a new ADR rather than editing history.
