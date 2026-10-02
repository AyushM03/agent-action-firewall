"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useApproverSession, useApproverToken } from "@/lib/approver-session";
import { formatTimestamp } from "@/lib/format";
import { ApiError, getRequestHistory } from "@/services/api";
import type { RequestHistory } from "@/types/api";

type State = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; history: RequestHistory };

/** What the agent asked for, exactly as submitted, and every event the request produced. */
export function RequestDetail({ requestId }: { requestId: string }) {
  const token = useApproverToken();
  const { signOut } = useApproverSession();
  const [state, setState] = useState<State>({ status: "loading" });

  const fetchHistory = useCallback(
    () =>
      getRequestHistory(token, requestId).then(
        (history) => setState({ status: "ready", history }),
        (err) => {
          if (err instanceof ApiError && err.status === 401) return signOut();
          setState({ status: "error", message: err instanceof Error ? err.message : "Failed to load the request." });
        },
      ),
    [token, requestId, signOut],
  );

  useEffect(() => {
    void fetchHistory();
  }, [fetchHistory]);

  function retry() {
    setState({ status: "loading" });
    void fetchHistory();
  }

  if (state.status === "loading") {
    return <div className="h-32 animate-pulse rounded-md bg-slate-100" aria-busy="true" aria-label="Loading request" />;
  }
  if (state.status === "error") {
    return <ErrorState title="Couldn't load this request." message={state.message} onRetry={retry} />;
  }

  const { history } = state;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <section className="min-w-0">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Requested payload</h3>
        <pre className="mt-2 overflow-x-auto rounded-md bg-slate-50 p-3 font-mono text-xs leading-relaxed ring-1 ring-slate-200">
          {JSON.stringify(history.payload, null, 2)}
        </pre>
        <p className="mt-2 break-all font-mono text-[11px] text-muted">request {history.request_id}</p>
      </section>

      <section className="min-w-0">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Event history</h3>
        <ol className="mt-2 space-y-3 border-l border-slate-200 pl-4">
          {history.events.map((event) => (
            <li key={event.id} className="text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={event.event_type} />
                <time dateTime={event.created_at} className="font-mono text-xs text-muted">
                  {formatTimestamp(event.created_at)}
                </time>
                <span className="font-mono text-xs text-muted">{event.actor}</span>
              </div>
              <p className="mt-1">{event.reason}</p>
              {Object.keys(event.data).length > 0 && (
                <pre className="mt-1 overflow-x-auto rounded bg-slate-50 px-2 py-1 font-mono text-[11px] text-muted ring-1 ring-slate-200">
                  {JSON.stringify(event.data, null, 2)}
                </pre>
              )}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
