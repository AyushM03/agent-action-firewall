import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 items-center justify-center px-4">
      <div className="rounded-card border border-slate-200 bg-surface px-8 py-6 text-center shadow-sm">
        <h1 className="text-xl font-semibold text-foreground">Agent Action Firewall</h1>
        <p className="mt-2 text-sm text-muted">
          The full dashboard lands in Phase 7. The approval queue is available now.
        </p>
        <Link href="/approvals" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">
          Go to pending approvals →
        </Link>
      </div>
    </main>
  );
}
