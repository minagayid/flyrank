import OpenAI from "openai";
import type { FlowNodeData } from "./types";

export type DecisionProvider = "mock" | "openai";

export function configuredProvider(): DecisionProvider {
  return process.env.DECISION_PROVIDER === "openai" && process.env.OPENAI_API_KEY ? "openai" : "mock";
}

export async function decide(data: FlowNodeData, input: string): Promise<"YES" | "NO"> {
  if (configuredProvider() === "mock") return data.mockDecision === "NO" ? "NO" : "YES";

  const client = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
    baseURL: process.env.OPENAI_BASE_URL || undefined,
  });
  const response = await client.chat.completions.create({
    model: process.env.OPENAI_MODEL || "gpt-4o-mini",
    temperature: 0,
    max_tokens: 8,
    messages: [
      { role: "system", content: "Evaluate the decision prompt. Return exactly one token: YES or NO. Do not explain." },
      { role: "user", content: `Decision prompt: ${data.prompt}\nInput: ${input}` },
    ],
  });
  const answer = response.choices[0]?.message.content?.trim().toUpperCase();
  if (answer !== "YES" && answer !== "NO") {
    throw new Error("The configured model must return exactly YES or NO.");
  }
  return answer;
}
