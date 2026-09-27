import { z } from "zod";
import { qualifyLead, type QualificationResult } from "./qualifier";

export const qualifyLeadInput = z.object({
  company: z.string().trim().max(120).optional(),
  service: z.string().trim().max(80).optional(),
  budget: z.string().trim().max(80).optional(),
  timeline: z.string().trim().max(80).optional(),
  description: z.string().trim().min(8).max(1200),
  question: z.string().trim().min(1).max(400),
});

export type QualifyLeadInput = z.infer<typeof qualifyLeadInput>;

export type QualifyLeadOutput = QualificationResult & {
  resultKind: "lead-qualification";
};

export async function executeQualifyLead(input: QualifyLeadInput): Promise<QualifyLeadOutput> {
  const result = qualifyLead(input);
  if (!Number.isFinite(result.score)) throw new Error("The model returned an invalid score.");
  return { ...result, resultKind: "lead-qualification" };
}
