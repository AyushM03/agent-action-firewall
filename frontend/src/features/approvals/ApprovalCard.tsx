"use client";

import { useState } from "react";

import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import type { PendingApproval } from "@/types/api";

type Props = {
  item: PendingApproval;
  busy: boolean;
  error: string | null;
  onResolve: (decision: "approve" | "reject", note: string) => void;
};

export function ApprovalCard({ item, busy, error, onResolve }: Props) {
  const [note, setNote] = useState("");

  return (
    <article className="rounded-card border border-slate-200 bg-surface p-4 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-semibold">{item.action_type}</span>
            <StatusBadge status="needs_approval" />
          </div>
          <p className="mt-1 text-sm text-muted">
            requested by <span className="font-medium text-foreground">{item.agent_name}</span>
          </p>
        </div>
        <time dateTime={item.requested_at} className="font-mono text-xs text-muted">
          {new Date(item.requested_at).toLocaleString()}
        </time>
      </header>

      <p className="mt-3 text-sm">
        <span className="text-muted">Reason: </span>
        {item.reason}
      </p>

      <pre className="mt-3 overflow-x-auto rounded-md bg-slate-50 p-3 font-mono text-xs leading-relaxed ring-1 ring-slate-200">
        {JSON.stringify(item.payload, null, 2)}
      </pre>

      <p className="mt-2 break-all font-mono text-[11px] text-muted">request {item.request_id}</p>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          aria-label="Note (optional)"
          placeholder="Note (optional)"
          maxLength={500}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={busy}
          className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        />
        <div className="flex gap-2">
          <Button variant="destructive" disabled={busy} onClick={() => onResolve("reject", note)}>
            Reject
          </Button>
          <Button disabled={busy} onClick={() => onResolve("approve", note)}>
            {busy ? "Saving…" : "Approve"}
          </Button>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-sm text-status-denied">
          {error}
        </p>
      )}
    </article>
  );
}
