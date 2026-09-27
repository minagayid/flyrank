import { describe, expect, it } from "vitest";
import { extractFeatures } from "./features";

describe("lead feature extraction", () => {
  it("recognizes a comma-separated structured budget", () => {
    expect(extractFeatures({ description: "A clear redesign scope.", budget: "$8,000" })).toMatchObject({ budget_stated: 1, budget_fit: 1 });
  });

  it("recognizes a comma-separated amount in free text", () => {
    expect(extractFeatures({ description: "The owner approved $12,000 for the launch." }).budget_fit).toBe(1);
  });

  it("does not invent a fit band when the budget is absent", () => {
    expect(extractFeatures({ description: "A clear redesign scope with an active proposal." })).toMatchObject({ budget_stated: 0, budget_fit: 0 });
  });

  it("recognizes a speculative request and missing timeline", () => {
    expect(extractFeatures({ description: "This is a free student project and we might start next year." })).toMatchObject({ free_or_speculative: 1, early_stage: 1, timeline_defined: 0 });
  });
});
