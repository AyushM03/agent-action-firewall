# Security Requirements

## Authentication
The approval dashboard requires authentication. No unauthenticated user can approve or reject actions.

## Authorization
Only the designated approver role can approve/reject. Agents can only submit action requests for action types they're registered for.

## Secrets
Gmail OAuth credentials and Stripe API keys live only in backend environment variables. They are never sent to the frontend, logged, or committed to Git.

## Database
- The audit_log table is append-only at the application layer (and ideally enforced with DB-level permissions/triggers, not just convention).
- Use least-privilege DB credentials for the backend service.

## Input Validation
All action request payloads are validated server-side (type, required fields, action type must exist in policy config) — never trust the frontend's validation alone.

## APIs
Validate request bodies and parameters on every endpoint, especially the approval endpoints (can't approve a request that doesn't exist or was already resolved).

## Third-Party Integrations
- Gmail: use the minimal scope needed to send mail (not full inbox access).
- Stripe: use test-mode keys only for this project; never wire in live keys.

Security is part of the core pitch of this project (it's a firewall) — it should be designed in from Phase 1, not bolted on before deployment.
