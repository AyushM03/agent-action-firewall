"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { ApproverSessionProvider, useApproverSession } from "@/lib/approver-session";

import { Button } from "./Button";
import { LoginForm } from "./LoginForm";

const NAV = [
  { href: "/agents", label: "Agents" },
  { href: "/approvals", label: "Approvals" },
  { href: "/audit", label: "Audit log" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <ApproverSessionProvider>
      <Header />
      <Gate>{children}</Gate>
    </ApproverSessionProvider>
  );
}

function Header() {
  const pathname = usePathname();
  const { session, signOut } = useApproverSession();

  return (
    <header className="border-b border-slate-200 bg-surface">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/agents" className="font-mono text-sm font-semibold tracking-tight">
          agent-action-firewall
        </Link>
        {session.status === "signed_in" && (
          <>
            <nav className="flex gap-1 text-sm">
              {NAV.map(({ href, label }) => {
                const active = pathname === href || pathname.startsWith(`${href}/`);
                return (
                  <Link
                    key={href}
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
                      active ? "bg-primary/10 text-primary" : "text-muted hover:bg-slate-100 hover:text-foreground"
                    }`}
                  >
                    {label}
                  </Link>
                );
              })}
            </nav>
            <div className="ml-auto flex items-center gap-2 text-sm">
              <span className="text-muted">
                Signed in as <span className="font-medium text-foreground">{session.username}</span>
              </span>
              <Button variant="secondary" onClick={signOut}>
                Sign out
              </Button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}

function Gate({ children }: { children: ReactNode }) {
  const { session, signIn } = useApproverSession();

  let content: ReactNode = children;
  if (session.status === "checking") content = <p className="text-sm text-muted">Checking session…</p>;
  if (session.status === "signed_out") content = <LoginForm onLoggedIn={signIn} />;

  return <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{content}</main>;
}
