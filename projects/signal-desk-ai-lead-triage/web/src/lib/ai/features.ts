export const FEATURE_KEYS = [
  "budget_stated",
  "budget_fit",
  "decision_maker",
  "concrete_scope",
  "service_fit",
  "timeline_defined",
  "near_term",
  "funding_intent",
  "free_or_speculative",
  "early_stage",
  "unrealistic_timing",
  "active_engagement",
] as const;

export type FeatureKey = (typeof FEATURE_KEYS)[number];
export type FeatureVector = Record<FeatureKey, number>;

export type LeadForScoring = {
  company?: string;
  description: string;
  service?: string;
  budget?: string;
  timeline?: string;
};

const patterns: Record<FeatureKey, RegExp> = {
  budget_stated: /(\$\s?\d|\b(?:budget|budgeted|allocated|approved)\b|\b\d{1,3}(?:,\d{3})+\b)/i,
  budget_fit: /(\$\s?(?:[5-9]\d{3}|[1-9]\d{4,})|\b(?:5k|6k|7k|8k|9k|10k|12k|15k|20k)\b)/i,
  decision_maker: /\b(?:founder|owner|co-founder|director|partner|head of|i decide|decision maker|our ceo)\b/i,
  concrete_scope: /\b(?:redesign|launch|migration|shopify|checkout|booking|brand identity|landing page|website|seo audit|campaign|prototype|dashboard|conversion|catalogue|catalog)\b/i,
  service_fit: /\b(?:web|website|brand|shopify|e-?commerce|seo|design|conversion|product|content|campaign|digital)\b/i,
  timeline_defined: /\b(?:by (?:the )?(?:end of|first week|next month|june|july|august|september|october|november|december)|within \d+ weeks?|in \d+ weeks?|\d+[- ]week|next quarter|this quarter|launch date|deadline|timeline)\b/i,
  near_term: /\b(?:next week|within (?:two|three|four|2|3|4) weeks?|in (?:two|three|four|2|3|4) weeks?|this month|asap|soon|launching next month)\b/i,
  funding_intent: /\b(?:approved|allocated|signed off|ready to invest|funded|budget is set|deposit|purchase order|po approved)\b/i,
  free_or_speculative: /\b(?:free|for exposure|unpaid|portfolio piece|just for practice|no budget|volunteer|do it for a cut|equity only)\b/i,
  early_stage: /\b(?:just an idea|exploring|exploratory|researching options|not sure yet|maybe next year|no rush|student project|school project|learning project)\b/i,
  unrealistic_timing: /\b(?:by tomorrow|overnight|in the next 24 hours|today if possible|in one day)\b/i,
  active_engagement: /\b(?:book a call|schedule a call|ready to start|kick ?off|next step|proposal|statement of work|sow|discovery call|send a quote)\b/i,
};

export function extractFeatures(lead: LeadForScoring): FeatureVector {
  const content = [lead.company, lead.service, lead.budget, lead.timeline, lead.description]
    .filter(Boolean)
    .join(" ");

  const vector = Object.fromEntries(
    FEATURE_KEYS.map((key) => [
      key,
      patterns[key].test(key === "budget_fit" ? content.replace(/,/g, "") : content) ? 1 : 0,
    ]),
  ) as FeatureVector;

  if (lead.timeline && /(?:within 4 weeks|within 3 weeks|within 2 weeks|next week|this month)/i.test(lead.timeline)) vector.near_term = 1;
  return vector;
}

export const FEATURE_COPY: Record<FeatureKey, { positive: string; negative?: string }> = {
  budget_stated: { positive: "The request names a budget or allocated funds." },
  budget_fit: { positive: "The stated range may support a scoped studio project." },
  decision_maker: { positive: "A decision-maker appears to be involved." },
  concrete_scope: { positive: "The request names a concrete deliverable." },
  service_fit: { positive: "The work appears to match the studio's services." },
  timeline_defined: { positive: "A target date or timeframe is described." },
  near_term: { positive: "The timeline is relatively near-term." },
  funding_intent: { positive: "The request describes a funded or approved project." },
  free_or_speculative: { positive: "The request signals free or speculative work.", negative: "Free or speculative work is requested." },
  early_stage: { positive: "The request sounds exploratory or early-stage.", negative: "The project is still exploratory." },
  unrealistic_timing: { positive: "The requested delivery window may be unrealistic.", negative: "The requested delivery window may be unrealistic." },
  active_engagement: { positive: "The sender is asking for a concrete next step." },
};
