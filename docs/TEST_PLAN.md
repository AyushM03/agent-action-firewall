# Test Plan

## Policy Engine
- A whitelisted action for an agent is auto-allowed
- A blacklisted action is auto-denied with a clear reason
- An action matching a "needs approval" rule is queued, not executed
- Policy evaluation never has side effects (can be tested as a pure function)

## Rate Limiting
- N requests within the configured window succeed
- Request N+1 within the same window is denied
- Counter resets correctly after the window expires
- Rate limit denial is written to the audit log with reason "rate_limited"

## Approval Workflow
- A pending action appears in the approval queue
- An unauthenticated request cannot approve/reject
- Approving executes the underlying action (Gmail/Stripe)
- Rejecting does not execute the action, and is logged

## Audit Log
- Every request produces exactly one audit event
- The audit log cannot be updated or deleted (verify at the DB layer)
- Log entries are queryable by agent, action type, and decision

## Executors
- Gmail: a real test email is sent and its message ID is recorded
- Stripe: a test-mode charge/payment intent is created and its ID is recorded
- A failed executor call (e.g. bad Gmail token) logs a distinct "execution_failed" event, separate from "denied"

## End-to-End
- Agent requests risky action → queued → approved → email actually sent → audit trail shows the full chain
- Agent exceeds rate limit → denied → no execution → audit trail reflects denial

This becomes your testing checklist once implementation starts.
