"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState, ErrorState, LoadingBlocks } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useApproverSession, useApproverToken } from "@/lib/approver-session";
import { ApiError, listPendingApprovals, resolveApproval } from "@/services/api";
import type { PendingApproval, Resolution } from "@/types/api";

import { ApprovalCard } from "./ApprovalCard";

type Queue =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; items: PendingApproval[] };

export function ApprovalQueue() {
  const token = useApproverToken();
  const { signOut } = useApproverSession();
  const [queue, setQueue] = useState<Queue>({ status: "loading" });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [itemErrors, setItemErrors] = useState<Record<string, string>>({});
  const [recent, setRecent] = useState<Resolution[]>([]);

  const loadQueue = useCallback(async () => {
    setQueue({ status: "loading" });
    try {
      setQueue({ status: "ready", items: await listPendingApprovals(token) });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return signOut();
      setQueue({ status: "error", message: err instanceof Error ? err.message : "Failed to load approvals." });
    }
  }, [token, signOut]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  async function handleResolve(requestId: string, decision: "approve" | "reject", note: string) {
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
        void loadQueue();
        return;
      }
      setItemErrors((prev) => ({ ...prev, [requestId]: err instanceof Error ? err.message : "Failed to save." }));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Pending approvals</h1>
          <p className="text-sm text-muted">
            Agent actions held by policy until a human decides. Every decision is written to the audit log.
          </p>
        </div>
        <Button variant="secondary" onClick={loadQueue} disabled={queue.status === "loading"}>
          Refresh
        </Button>
      </div>

      {queue.status === "loading" && <LoadingBlocks height="h-40" label="Loading approvals" />}

      {queue.status === "error" && (
        <ErrorState title="Couldn't load the approval queue." message={queue.message} onRetry={loadQueue} />
      )}

      {queue.status === "ready" && queue.items.length === 0 && (
        <EmptyState title="No pending approvals" hint="Actions that need a human decision will show up here." />
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
