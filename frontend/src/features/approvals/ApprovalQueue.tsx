"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { clearToken, getToken, setToken } from "@/lib/session";
import { ApiError, getMe, listPendingApprovals, resolveApproval } from "@/services/api";
import type { PendingApproval, Resolution } from "@/types/api";

import { ApprovalCard } from "./ApprovalCard";
import { LoginForm } from "./LoginForm";

type Session = { status: "checking" } | { status: "signed_out" } | { status: "signed_in"; token: string; username: string };

type Queue =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; items: PendingApproval[] };

export function ApprovalQueue() {
  const [session, setSession] = useState<Session>({ status: "checking" });
  const [queue, setQueue] = useState<Queue>({ status: "loading" });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [itemErrors, setItemErrors] = useState<Record<string, string>>({});
  const [recent, setRecent] = useState<Resolution[]>([]);

  const signOut = useCallback(() => {
    clearToken();
    setSession({ status: "signed_out" });
  }, []);

  const startSession = useCallback(
    async (token: string) => {
      try {
        const me = await getMe(token);
        setToken(token);
        setSession({ status: "signed_in", token, username: me.username });
      } catch {
        signOut();
      }
    },
    [signOut],
  );

  const loadQueue = useCallback(
    async (token: string) => {
      setQueue({ status: "loading" });
      try {
        setQueue({ status: "ready", items: await listPendingApprovals(token) });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return signOut();
        setQueue({ status: "error", message: err instanceof Error ? err.message : "Failed to load approvals." });
      }
    },
    [signOut],
  );

  useEffect(() => {
    const token = getToken();
    if (token) void startSession(token);
    else signOut();
  }, [startSession, signOut]);

  const token = session.status === "signed_in" ? session.token : null;
  useEffect(() => {
    if (token) void loadQueue(token);
  }, [token, loadQueue]);

  async function handleResolve(requestId: string, decision: "approve" | "reject", note: string) {
    if (!token) return;
    setBusyId(requestId);
    setItemErrors((prev) => {
      const next = { ...prev };
      delete next[requestId];
      return next;
    });
    try {
      const resolution = await resolveApproval(token, requestId, decision, note);
      setRecent((prev) => [resolution, ...prev].slice(0, 5));
      setQueue((prev) =>
        prev.status === "ready" ? { ...prev, items: prev.items.filter((i) => i.request_id !== requestId) } : prev,
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return signOut();
      if (err instanceof ApiError && err.status === 409) {
        // Someone else resolved it first; the list is stale.
        void loadQueue(token);
        return;
      }
      setItemErrors((prev) => ({ ...prev, [requestId]: err instanceof Error ? err.message : "Failed to save." }));
    } finally {
      setBusyId(null);
    }
  }

  if (session.status === "checking") {
    return <p className="text-sm text-muted">Checking session…</p>;
  }
  if (session.status === "signed_out") {
    return <LoginForm onLoggedIn={startSession} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Pending approvals</h1>
          <p className="text-sm text-muted">
            Agent actions held by policy until a human decides. Every decision is written to the audit log.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted">
            Signed in as <span className="font-medium text-foreground">{session.username}</span>
          </span>
          <Button variant="secondary" onClick={() => loadQueue(session.token)} disabled={queue.status === "loading"}>
            Refresh
          </Button>
          <Button variant="secondary" onClick={signOut}>
            Sign out
          </Button>
        </div>
      </div>

      {queue.status === "loading" && (
        <div className="space-y-3" aria-busy="true" aria-label="Loading approvals">
          {[0, 1].map((i) => (
            <div key={i} className="h-40 animate-pulse rounded-card border border-slate-200 bg-surface" />
          ))}
        </div>
      )}

      {queue.status === "error" && (
        <div role="alert" className="rounded-card border border-status-denied/30 bg-status-denied/5 p-4 text-sm">
          <p className="font-medium text-status-denied">Couldn&apos;t load the approval queue.</p>
          <p className="mt-1 text-muted">{queue.message}</p>
          <Button variant="secondary" className="mt-3" onClick={() => loadQueue(session.token)}>
            Try again
          </Button>
        </div>
      )}

      {queue.status === "ready" && queue.items.length === 0 && (
        <div className="rounded-card border border-dashed border-slate-300 bg-surface p-8 text-center">
          <p className="font-medium">No pending approvals</p>
          <p className="mt-1 text-sm text-muted">Actions that need a human decision will show up here.</p>
        </div>
      )}

      {queue.status === "ready" && queue.items.length > 0 && (
        <div className="space-y-3">
          {queue.items.map((item) => (
            <ApprovalCard
              key={item.request_id}
              item={item}
              busy={busyId === item.request_id}
              error={itemErrors[item.request_id] ?? null}
              onResolve={(decision, note) => handleResolve(item.request_id, decision, note)}
            />
          ))}
        </div>
      )}

      {recent.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-muted">Resolved this session</h2>
          <ul className="mt-2 divide-y divide-slate-200 rounded-card border border-slate-200 bg-surface">
            {recent.map((r) => (
              <li key={r.request_id} className="px-4 py-2 text-sm">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <StatusBadge status={r.event_type} />
                  <span className="min-w-0 flex-1">{r.reason}</span>
                  <time dateTime={r.created_at} className="font-mono text-xs text-muted">
                    {new Date(r.created_at).toLocaleTimeString()}
                  </time>
                </div>
                {r.execution && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 pl-1">
                    <StatusBadge status={r.execution.status} />
                    <span className="min-w-0 flex-1 text-muted">{r.execution.reason}</span>
                    {r.execution.external_id && (
                      <span className="break-all font-mono text-xs text-muted">{r.execution.external_id}</span>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
