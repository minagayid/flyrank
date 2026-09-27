import { notFound } from "next/navigation";
import { LeadWorkspace } from "@/components/lead/lead-workspace";
import { getLeadById } from "@/lib/data/leads";

export default async function LeadPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const lead = getLeadById(id);

  if (!lead) notFound();

  return <LeadWorkspace lead={lead} />;
}
