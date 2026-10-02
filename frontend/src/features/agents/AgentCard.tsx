import Link from "next/link";
import type { ReactNode } from "react";

import { formatRelative, formatTimestamp } from "@/lib/format";
import type { AgentActivity, EventType } from "@/types/api";

const COUNTS: { type: EventType; label: string; className: string }[] = [
  { type: "allowed", label: "Allowed", className: "text-status-allowed" },
  { type: "denied", label: "Denied", className: "text-status-denied" },
  { type: "needs_approval", label: "Held", className: "text-status-needs-approval" },
  { type: "executed", label: "Executed", className: "text-status-allowed" },
  { type: "execution_failed", label: "Failed", className: "text-status-denied" },
];

export function AgentCard({ agent }: { agent: AgentActivity }) {
  const auditHref = `/audit?agent_id=${encodeURIComponent(agent.id)}`;

  return (
    <article className="flex flex-col rounded-card border border-slate-200 bg-surface p-4 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-mono text-sm font-semibold">{agent.name}</h3>
          {agent.description && <p className="mt-0.5 text-sm text-muted">{agent.description}</p>}
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Pill className={agent.is_active ? "text-status-allowed ring-status-allowed/30" : "text-muted ring-slate-300"}>
            {agent.is_active ? "Active" : "Inactive"}
          </Pill>
          {!agent.has_api_key && <Pill className="text-status-needs-approval ring-status-needs-approval/30">No API key</Pill>}
        </div>
      </header>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {agent.allowed_action_types.length > 0 ? (
          agent.allowed_action_types.map((type) => (
            <span key={type} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-foreground">
              {type}
            </span>
          ))
        ) : (
          <span className="text-xs text-muted">No action types registered</span>
        )}
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-px overflow-hidden rounded-md bg-slate-200 text-center sm:grid-cols-6">
        <Stat label="Requests" value={agent.total_requests} className="text-foreground" />
        {COUNTS.map(({ type, label, className }) => (
          <Stat key={type} label={label} value={agent.event_counts[type] ?? 0} className={className} />
        ))}
      </dl>

      <footer className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-muted">
          Last activity{" "}
          {agent.last_activity_at ? (
            <time dateTime={agent.last_activity_at} title={formatTimestamp(agent.last_activity_at)} className="text-foreground">
              {formatRelative(agent.last_activity_at)}
            </time>
          ) : (
            <span className="text-foreground">never</span>
          )}
        </span>
        <span className="flex gap-4">
          {agent.pending_approvals > 0 && (
            <Link href="/approvals" className="font-medium text-status-needs-approval hover:underline">
              {agent.pending_approvals} awaiting approval
            </Link>
          )}
          <Link href={auditHref} className="font-medium text-primary hover:underline">
            View log →
          </Link>
        </span>
      </footer>
    </article>
  );
}

function Stat({ label, value, className }: { label: string; value: number; className: string }) {
  return (
    <div className="bg-surface px-2 py-2">
      <dt className="text-[11px] text-muted">{label}</dt>
      <dd className={`font-mono text-base font-semibold ${value === 0 ? "text-slate-300" : className}`}>{value}</dd>
    </div>
  );
}

function Pill({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}>
      {children}
    </span>
  );
}
