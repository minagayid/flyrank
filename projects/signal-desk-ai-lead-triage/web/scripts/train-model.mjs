import { readFile, writeFile } from "node:fs/promises";

const source = new URL("../src/lib/ai/training-examples.json", import.meta.url);
const destination = new URL("../src/lib/ai/model-weights.json", import.meta.url);
const examples = JSON.parse(await readFile(source, "utf8"));

const patterns = {
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

const names = Object.keys(patterns);
const vectors = examples.map(({ text }) => [1, ...names.map((name) => Number(patterns[name].test(name === "budget_fit" ? text.replace(/,/g, "") : text)))]);
const labels = examples.map(({ label }) => label);
const weights = Array(vectors[0].length).fill(0);
const rate = 0.18;
const l2 = 0.02;

function sigmoid(value) {
  return 1 / (1 + Math.exp(-Math.max(-12, Math.min(12, value))));
}

for (let epoch = 0; epoch < 900; epoch += 1) {
  const gradients = Array(weights.length).fill(0);
  for (let row = 0; row < vectors.length; row += 1) {
    const estimate = sigmoid(vectors[row].reduce((sum, value, index) => sum + value * weights[index], 0));
    for (let col = 0; col < weights.length; col += 1) gradients[col] += (estimate - labels[row]) * vectors[row][col];
  }
  for (let col = 0; col < weights.length; col += 1) {
    const penalty = col === 0 ? 0 : l2 * weights[col];
    weights[col] -= rate * (gradients[col] / vectors.length + penalty);
  }
}

const result = {
  method: "logistic-regression",
  version: 1,
  trainedOn: "synthetic-curated-examples-v1",
  exampleCount: examples.length,
  intercept: Number(weights[0].toFixed(5)),
  weights: Object.fromEntries(names.map((name, index) => [name, Number(weights[index + 1].toFixed(5))])),
};

await writeFile(destination, `${JSON.stringify(result, null, 2)}\n`, "utf8");
process.stdout.write(`Trained ${result.method} on ${result.exampleCount} synthetic examples; wrote ${destination.pathname}\n`);
