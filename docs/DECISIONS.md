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

This file prevents the AI coding tool from silently changing these decisions later — if a change is needed, add a new ADR rather than editing history.
