// Shapes returned by the FastAPI backend (backend/app/api/).

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};

export type Approver = {
  username: string;
};

export type PendingApproval = {
  request_id: string;
  agent_id: string;
  agent_name: string;
  action_type: string;
  payload: Record<string, unknown>;
  reason: string;
  requested_at: string;
};

export type Execution = {
  status: "executed" | "execution_failed";
  reason: string;
  external_id: string | null;
  code: string | null;
};

export type Resolution = {
  request_id: string;
  event_type: "approved" | "rejected";
  reason: string;
  actor: string;
  created_at: string;
  // Set when approved: the result of running the action (Gmail send / Stripe payment).
  execution: Execution | null;
};

export type EventType =
  | "allowed"
  | "denied"
  | "needs_approval"
  | "approved"
  | "rejected"
  | "executed"
  | "execution_failed";

export type AuditEvent = {
  id: number;
  request_id: string;
  agent_id: string;
  agent_name: string;
  action_type: string;
  event_type: EventType;
  reason: string;
  // "firewall", "approver:<username>", "executor:gmail", ...
  actor: string;
  data: Record<string, unknown>;
  created_at: string;
};

export type AuditPage = {
  items: AuditEvent[];
  // Pass back as `before` for the next (older) page; null when there are no more.
  next_before: number | null;
};

export type AuditFilters = {
  agent_id?: string;
  action_type?: string;
  event_type?: EventType;
};

export type RequestHistory = {
  request_id: string;
  agent_id: string;
  agent_name: string;
  action_type: string;
  payload: Record<string, unknown>;
  requested_at: string;
  events: AuditEvent[];
};

export type AgentActivity = {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  allowed_action_types: string[];
  has_api_key: boolean;
  total_requests: number;
  pending_approvals: number;
  event_counts: Partial<Record<EventType, number>>;
  last_activity_at: string | null;
};
