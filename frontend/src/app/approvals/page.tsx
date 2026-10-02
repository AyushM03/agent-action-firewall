import type { Metadata } from "next";

import { ApprovalQueue } from "@/features/approvals/ApprovalQueue";

export const metadata: Metadata = {
  title: "Approvals · Agent Action Firewall",
};

export default function ApprovalsPage() {
  return <ApprovalQueue />;
}
