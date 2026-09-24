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

This file prevents the AI coding tool from silently changing these decisions later — if a change is needed, add a new ADR rather than editing history.
