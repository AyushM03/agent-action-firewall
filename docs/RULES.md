# Development Rules

## General
- Use TypeScript on the frontend, typed Python (Pydantic models) on the backend.
- Reuse existing components/services — don't duplicate logic across executors.
- Keep functions small; one policy rule = one evaluator function.
- Do not modify unrelated files.

## Before Coding
- Read PRD.md, ARCHITECTURE.md, and TASKS.md before implementing anything.
- Inspect existing policy/ratelimit/executor code before adding new logic.
- For any change touching the audit log schema, check DECISIONS.md first — this is a append-only, event-sourced table and changes are not casual.

## Backend (FastAPI)
- Route handlers must stay thin — delegate to `policy/`, `ratelimit/`, `executors/`.
- Every action request must produce exactly one audit event, regardless of outcome (allow/deny/error).
- Never call Gmail or Stripe from anywhere except `executors/`.
- Policy evaluation must never have side effects (no DB writes, no external calls) — it only returns a decision.

## Frontend (Next.js)
- Follow DESIGN.md for status colors and badge components.
- Dashboard reads should hit backend read endpoints only — never query Postgres/Redis directly.
- Include loading, empty, and error states for every data view.

## Security
- Gmail OAuth tokens and Stripe keys live only in backend env vars — never sent to or stored on the frontend.
- Validate every incoming action request payload server-side, even if the frontend already validated it.
- The approval endpoint must verify the approver is authenticated — no unauthenticated approvals, ever.

## Testing
- Every policy rule needs at least one test that proves it allows and one that proves it denies.
- Run tests after implementing each task, not just at the end.
- Fix failing tests before moving to the next task.

## Git
- Small commits, one task per commit where possible.
- Descriptive messages, e.g. `feat(policy): add rate-limit rule evaluator`.
