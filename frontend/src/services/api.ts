import type {
  AgentActivity,
  Approver,
  AuditFilters,
  AuditPage,
  PendingApproval,
  RequestHistory,
  Resolution,
  TokenResponse,
} from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit & { token?: string | null } = {}): Promise<T> {
  const { token, headers, ...rest } = init;
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    });
  } catch {
    throw new ApiError(0, "Can't reach the firewall API. Is the backend running?");
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export function login(username: string, password: string): Promise<TokenResponse> {
  return request("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
}

export function getMe(token: string): Promise<Approver> {
  return request("/auth/me", { token });
}

export function listPendingApprovals(token: string): Promise<PendingApproval[]> {
  return request("/approvals/pending", { token });
}

export function resolveApproval(
  token: string,
  requestId: string,
  decision: "approve" | "reject",
  note?: string,
): Promise<Resolution> {
  return request(`/approvals/${encodeURIComponent(requestId)}/${decision}`, {
    method: "POST",
    token,
    body: JSON.stringify({ note: note?.trim() || null }),
  });
}

export function listAuditEvents(
  token: string,
  filters: AuditFilters,
  page: { before?: number; limit?: number } = {},
): Promise<AuditPage> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...filters, ...page })) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return request(`/audit/events${query ? `?${query}` : ""}`, { token });
}

export function getRequestHistory(token: string, requestId: string): Promise<RequestHistory> {
  return request(`/audit/requests/${encodeURIComponent(requestId)}`, { token });
}

export function listAgents(token: string): Promise<AgentActivity[]> {
  return request("/agents", { token });
}
