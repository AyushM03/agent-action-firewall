import type { Metadata } from "next";

import { AgentActivityView } from "@/features/agents/AgentActivityView";

export const metadata: Metadata = {
  title: "Agents · Agent Action Firewall",
};

export default function AgentsPage() {
  return <AgentActivityView />;
}
