"use client";

import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { formatTimestamp } from "@/lib/format";
import type { AuditEvent } from "@/types/api";

import { RequestDetail } from "./RequestDetail";

/** The audit trail, newest at top. Every row shows timestamp, agent, action type, decision and reason (DESIGN.md).
 *  Clicking a row opens the full request: payload plus every event it produced. */
export function EventList({ events }: { events: AuditEvent[] }) {
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <ul className="divide-y divide-slate-200 rounded-card border border-slate-200 bg-surface">
      {events.map((event) => {
        const open = openId === event.id;
        return (
          <li key={event.id}>
            <button
              type="button"
              aria-expanded={open}
              onClick={() => setOpenId(open ? null : event.id)}
              className="grid w-full grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1 px-4 py-2.5 text-left text-sm hover:bg-slate-50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary md:grid-cols-[11rem_9rem_minmax(0,10rem)_8rem_1fr]"
            >
              <time dateTime={event.created_at} className="font-mono text-xs text-muted">
                {formatTimestamp(event.created_at)}
              </time>
              <span className="justify-self-start">
                <StatusBadge status={event.event_type} />
              </span>
              <span className="truncate font-medium">{event.agent_name}</span>
              <span className="truncate font-mono text-xs">{event.action_type}</span>
              <span className="col-span-2 min-w-0 text-muted md:col-span-1">
                <span className="block truncate" title={event.reason}>
                  {event.reason}
                </span>
              </span>
            </button>
            {open && (
              <div className="border-t border-slate-100 bg-background/60 px-4 py-4">
                <RequestDetail requestId={event.request_id} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
