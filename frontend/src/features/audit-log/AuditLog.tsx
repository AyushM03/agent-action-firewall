"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState, ErrorState, LoadingBlocks } from "@/components/States";
import { useApproverSession, useApproverToken } from "@/lib/approver-session";
import { ApiError, listAgents, listAuditEvents } from "@/services/api";
import type { AgentActivity, AuditEvent, AuditFilters, EventType } from "@/types/api";

import { EventList } from "./EventList";

const PAGE_SIZE = 50;

const EVENT_TYPES: { value: EventType; label: string }[] = [
  { value: "allowed", label: "Allowed" },
  { value: "denied", label: "Denied" },
  { value: "needs_approval", label: "Needs approval" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "executed", label: "Executed" },
  { value: "execution_failed", label: "Execution failed" },
];

type Log =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; items: AuditEvent[]; nextBefore: number | null };

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export function AuditLog() {
  const token = useApproverToken();
  const { signOut } = useApproverSession();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Filters live in the URL so a filtered view can be linked to (e.g. from the agents page).
  const agentId = searchParams.get("agent_id") ?? "";
  const actionType = searchParams.get("action_type") ?? "";
  const eventType = (searchParams.get("event_type") ?? "") as EventType | "";
  const filters = useMemo<AuditFilters>(
    () => ({ agent_id: agentId || undefined, action_type: actionType || undefined, event_type: eventType || undefined }),
    [agentId, actionType, eventType],
  );

  const [reloadKey, setReloadKey] = useState(0);
  // Results are tagged with the query they were loaded for. Anything else counts as loading,
  // which also discards responses for filters the user has already moved away from.
  const queryKey = `${agentId}|${actionType}|${eventType}|${reloadKey}`;
  const [result, setResult] = useState<{ key: string; log: Log } | null>(null);
  const [moreError, setMoreError] = useState<{ key: string; message: string } | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [agents, setAgents] = useState<AgentActivity[] | null>(null);
  const log: Log = result?.key === queryKey ? result.log : { status: "loading" };

  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) signOut();
    },
    [signOut],
  );

  useEffect(() => {
    let cancelled = false;
    listAgents(token)
      .then((list) => !cancelled && setAgents(list))
      .catch((err) => {
        handleError(err);
        // Filters still work by URL; the dropdown just can't list agent names.
        if (!cancelled) setAgents([]);
      });
    return () => {
      cancelled = true;
    };
  }, [token, handleError]);

  useEffect(() => {
    listAuditEvents(token, filters, { limit: PAGE_SIZE })
      .then((page) =>
        setResult({ key: queryKey, log: { status: "ready", items: page.items, nextBefore: page.next_before } }),
      )
      .catch((err) => {
        handleError(err);
        setResult({ key: queryKey, log: { status: "error", message: errorMessage(err, "Failed to load the audit log.") } });
      });
  }, [token, filters, queryKey, handleError]);

  async function loadMore() {
    if (log.status !== "ready" || log.nextBefore === null) return;
    const key = queryKey;
    setLoadingMore(true);
    setMoreError(null);
    try {
      const page = await listAuditEvents(token, filters, { before: log.nextBefore, limit: PAGE_SIZE });
      setResult((prev) =>
        prev?.key === key && prev.log.status === "ready"
          ? { key, log: { status: "ready", items: [...prev.log.items, ...page.items], nextBefore: page.next_before } }
          : prev,
      );
    } catch (err) {
      handleError(err);
      setMoreError({ key, message: errorMessage(err, "Failed to load more events.") });
    } finally {
      setLoadingMore(false);
    }
  }

  function setFilter(key: keyof AuditFilters, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  const actionTypes = useMemo(() => {
    const types = new Set((agents ?? []).flatMap((a) => a.allowed_action_types));
    if (actionType) types.add(actionType);
    return [...types].sort();
  }, [agents, actionType]);

  const hasFilters = Boolean(agentId || actionType || eventType);
  const selectClass =
    "mt-1 block w-full rounded-md border border-slate-300 bg-surface px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Audit log</h1>
          <p className="text-sm text-muted">
            Every decision, approval and execution, newest first. Entries are append-only and can&apos;t be edited.
          </p>
        </div>
        <Button variant="secondary" onClick={() => setReloadKey((k) => k + 1)} disabled={log.status === "loading"}>
          Refresh
        </Button>
      </div>

      <div className="grid gap-3 rounded-card border border-slate-200 bg-surface p-4 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end">
        <label className="text-xs font-medium text-muted">
          Agent
          <select className={selectClass} value={agentId} onChange={(e) => setFilter("agent_id", e.target.value)}>
            <option value="">All agents</option>
            {agentId && !agents?.some((a) => a.id === agentId) && <option value={agentId}>{agentId}</option>}
            {agents?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs font-medium text-muted">
          Action type
          <select className={selectClass} value={actionType} onChange={(e) => setFilter("action_type", e.target.value)}>
            <option value="">All action types</option>
            {actionTypes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs font-medium text-muted">
          Event
          <select className={selectClass} value={eventType} onChange={(e) => setFilter("event_type", e.target.value)}>
            <option value="">All events</option>
            {EVENT_TYPES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <Button variant="secondary" disabled={!hasFilters} onClick={() => router.replace(pathname, { scroll: false })}>
          Clear filters
        </Button>
      </div>

      {log.status === "loading" && <LoadingBlocks count={6} height="h-11" label="Loading audit log" />}

      {log.status === "error" && (
        <ErrorState
          title="Couldn't load the audit log."
          message={log.message}
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      )}

      {log.status === "ready" && log.items.length === 0 && (
        <EmptyState
          title={hasFilters ? "No events match these filters" : "No audit events yet"}
          hint={
            hasFilters
              ? "Try a different agent, action type or event."
              : "Events appear here as soon as an agent submits its first action request."
          }
        />
      )}

      {log.status === "ready" && log.items.length > 0 && (
        <div className="space-y-3">
          <EventList events={log.items} />
          <div className="flex flex-col items-center gap-2">
            {log.nextBefore !== null ? (
              <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? "Loading…" : "Load older events"}
              </Button>
            ) : (
              <p className="text-xs text-muted">Oldest event reached · {log.items.length} shown</p>
            )}
            {moreError?.key === queryKey && (
              <p role="alert" className="text-sm text-status-denied">
                {moreError.message}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
