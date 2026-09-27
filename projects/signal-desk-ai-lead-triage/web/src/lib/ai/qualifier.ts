import model from "./model-weights.json";
import { extractFeatures, FEATURE_COPY, FEATURE_KEYS, type FeatureKey, type LeadForScoring } from "./features";

export type QualificationResult = {
  score: number;
  label: "Strong signal" | "Needs context" | "Early or mismatched";
  explanation: string;
  supportingSignals: string[];
  cautions: string[];
  openQuestions: string[];
  featureContributions: Array<{ key: FeatureKey; contribution: number }>;
  model: string;
};

const sigmoid = (value: number) => 1 / (1 + Math.exp(-Math.max(-12, Math.min(12, value))));

export function qualifyLead(lead: LeadForScoring): QualificationResult {
  const features = extractFeatures(lead);
  const contributions = FEATURE_KEYS.map((key) => ({
    key,
    contribution: features[key] * (model.weights[key] ?? 0),
  }));
  const probability = sigmoid(model.intercept + contributions.reduce((sum, item) => sum + item.contribution, 0));
  const score = Math.round(probability * 100);
  const label = score >= 66 ? "Strong signal" : score >= 42 ? "Needs context" : "Early or mismatched";
  const sorted = [...contributions].filter((item) => item.contribution !== 0).sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  const supportingSignals = sorted.filter((item) => item.contribution > 0).slice(0, 3).map(({ key }) => FEATURE_COPY[key].positive);
  const cautions = sorted.filter((item) => item.contribution < 0).slice(0, 3).map(({ key }) => FEATURE_COPY[key].negative ?? FEATURE_COPY[key].positive);
  const openQuestions = [
    features.budget_stated ? null : "What budget range has been approved?",
    features.timeline_defined ? null : "When does the team need the first version?",
    features.concrete_scope ? null : "Which one outcome would make this project a success?",
  ].filter((item): item is string => Boolean(item)).slice(0, 2);

  return {
    score,
    label,
    explanation: supportingSignals[0] ?? cautions[0] ?? "There are not enough concrete details to form a useful signal yet.",
    supportingSignals,
    cautions,
    openQuestions,
    featureContributions: sorted,
    model: `${model.method} · ${model.exampleCount} synthetic examples`,
  };
}

export function draftReply(result: QualificationResult, question: string): string {
  const asksForQuestions = /question|ask|follow.?up|next step|reply/i.test(question);
  const positives = result.supportingSignals.length ? result.supportingSignals.join(" ") : "I found no strong positive signal in this request yet.";
  const cautions = result.cautions.length ? ` A point to clarify: ${result.cautions[0].toLowerCase()}` : "";
  if (asksForQuestions && result.openQuestions.length) {
    return `The model gives this request a ${result.score}/100 fit signal. ${result.openQuestions.map((item) => `You could ask: “${item}”`).join(" ")} These are suggestions to edit before using.`;
  }
  return `The model gives this request a ${result.score}/100 fit signal. ${positives}${cautions} This is a sorting aid trained on synthetic examples, so check the original request before deciding what to do.`;
}
