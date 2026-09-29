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

export type Resolution = {
  request_id: string;
  event_type: "approved" | "rejected";
  reason: string;
  actor: string;
  created_at: string;
};
