import type { Metadata } from "next";

import { ApprovalQueue } from "@/features/approvals/ApprovalQueue";

export const metadata: Metadata = {
  title: "Approvals · Agent Action Firewall",
};

export default function ApprovalsPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">
      <ApprovalQueue />
    </main>
  );
}
