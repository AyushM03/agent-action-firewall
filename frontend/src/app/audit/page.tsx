import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingBlocks } from "@/components/States";
import { AuditLog } from "@/features/audit-log/AuditLog";

export const metadata: Metadata = {
  title: "Audit log · Agent Action Firewall",
};

export default function AuditPage() {
  // AuditLog reads its filters from the URL (useSearchParams), which needs a Suspense boundary.
  return (
    <Suspense fallback={<LoadingBlocks count={6} height="h-11" label="Loading audit log" />}>
      <AuditLog />
    </Suspense>
  );
}
