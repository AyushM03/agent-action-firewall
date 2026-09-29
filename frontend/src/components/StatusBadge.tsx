export type Status = "allowed" | "denied" | "needs_approval" | "pending" | "approved" | "rejected";

const STYLES: Record<Status, { label: string; className: string }> = {
  allowed: { label: "Allowed", className: "bg-status-allowed/10 text-status-allowed ring-status-allowed/30" },
  approved: { label: "Approved", className: "bg-status-allowed/10 text-status-allowed ring-status-allowed/30" },
  denied: { label: "Denied", className: "bg-status-denied/10 text-status-denied ring-status-denied/30" },
  rejected: { label: "Rejected", className: "bg-status-denied/10 text-status-denied ring-status-denied/30" },
  needs_approval: {
    label: "Needs approval",
    className: "bg-status-needs-approval/10 text-status-needs-approval ring-status-needs-approval/30",
  },
  pending: { label: "Pending", className: "bg-status-pending/10 text-status-pending ring-status-pending/30" },
};

export function StatusBadge({ status }: { status: Status }) {
  const { label, className } = STYLES[status];
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}>
      {label}
    </span>
  );
}
