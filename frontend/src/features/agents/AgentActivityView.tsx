"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState, ErrorState, LoadingBlocks } from "@/components/States";
import { useApproverSession, useApproverToken } from "@/lib/approver-session";
import { ApiError, listAgents, listAuditEvents } from "@/services/api";
import type { AgentActivity, AuditEvent } from "@/types/api";

import { EventList } from "../audit-log/EventList";
import { AgentCard } from "./AgentCard";

const RECENT_COUNT = 10;

type Load<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: T };

export function AgentActivityView() {
  const token = useApproverToken();
  const { signOut } = useApproverSession();
  const [agents, setAgents] = useState<Load<AgentActivity[]>>({ status: "loading" });
  const [recent, setRecent] = useState<Load<AuditEvent[]>>({ status: "loading" });

  const fetchAll = useCallback(async () => {
    const fail = (err: unknown, fallback: string) => {
      if (err instanceof ApiError && err.status === 401) signOut();
      return { status: "error" as const, message: err instanceof Error ? err.message : fallback };
    };
    // Independent requests: one failing shouldn't blank the other.
    await Promise.all([
      listAgents(token).then(
        (data) => setAgents({ status: "ready", data }),
        (err) => setAgents(fail(err, "Failed to load agents.")),
      ),
      listAuditEvents(token, {}, { limit: RECENT_COUNT }).then(
        (page) => setRecent({ status: "ready", data: page.items }),
        (err) => setRecent(fail(err, "Failed to load recent activity.")),
      ),
    ]);
  }, [token, signOut]);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  function reload() {
    setAgents({ status: "loading" });
    setRecent({ status: "loading" });
    void fetchAll();
  }

  const busy = agents.status === "loading" || recent.status === "loading";

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Agents</h1>
          <p className="text-sm text-muted">Registered agents and everything they&apos;ve asked the firewall to do.</p>
        </div>
        <Button variant="secondary" onClick={reload} disabled={busy}>
          Refresh
        </Button>
      </div>

      <section aria-labelledby="agents-heading">
        <h2 id="agents-heading" className="sr-only">
          Agent activity
        </h2>
        {agents.status === "loading" && <LoadingBlocks count={2} height="h-44" label="Loading agents" />}
        {agents.status === "error" && (
          <ErrorState title="Couldn't load agents." message={agents.message} onRetry={reload} />
        )}
        {agents.status === "ready" && agents.data.length === 0 && (
          <EmptyState title="No agents registered" hint="Run `python -m app.seed` in backend/ to create the demo agents." />
        )}
        {agents.status === "ready" && agents.data.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2">
            {agents.data.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="recent-heading" className="space-y-3">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="recent-heading" className="text-sm font-semibold text-muted">
            Recent activity
          </h2>
          <Link href="/audit" className="text-sm font-medium text-primary hover:underline">
            Full audit log →
          </Link>
        </div>
        {recent.status === "loading" && <LoadingBlocks count={4} height="h-11" label="Loading recent activity" />}
        {recent.status === "error" && (
          <ErrorState title="Couldn't load recent activity." message={recent.message} onRetry={reload} />
        )}
        {recent.status === "ready" && recent.data.length === 0 && (
          <EmptyState
            title="No audit events yet"
            hint="Events appear here as soon as an agent submits its first action request."
          />
        )}
        {recent.status === "ready" && recent.data.length > 0 && <EventList events={recent.data} />}
      </section>
    </div>
  );
}
