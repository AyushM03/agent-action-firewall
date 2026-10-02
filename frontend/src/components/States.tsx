import { Button } from "./Button";

// Shared loading / empty / error states (DESIGN.md: required on every async view).

export function LoadingBlocks({ count = 2, height = "h-24", label }: { count?: number; height?: string; label: string }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label={label}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={`${height} animate-pulse rounded-card border border-slate-200 bg-surface`} />
      ))}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="rounded-card border border-dashed border-slate-300 bg-surface p-8 text-center">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted">{hint}</p>
    </div>
  );
}

export function ErrorState({ title, message, onRetry }: { title: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-card border border-status-denied/30 bg-status-denied/5 p-4 text-sm">
      <p className="font-medium text-status-denied">{title}</p>
      <p className="mt-1 text-muted">{message}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
