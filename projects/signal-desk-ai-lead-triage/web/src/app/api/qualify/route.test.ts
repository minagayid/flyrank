import { describe, expect, it } from "vitest";
import { POST } from "./route";

const body = {
  company: "Northline Objects",
  service: "Shopify redesign",
  budget: "$8,000",
  timeline: "Within 6 weeks",
  description: "The founder approved an $8,000 budget for a Shopify checkout redesign and would like a discovery call.",
  question: "What should I ask next?",
};

describe("qualification route", () => {
  it("rejects invalid input before opening a stream", async () => {
    const response = await POST(new Request("http://localhost/api/qualify", {
      method: "POST",
      body: JSON.stringify({ ...body, question: "" }),
      headers: { "content-type": "application/json" },
    }));
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ error: expect.stringContaining("description") });
  });

  it("streams the four tool states and assistant text with no provider", async () => {
    const response = await POST(new Request("http://localhost/api/qualify", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "content-type": "application/json" },
    }));
    const stream = await response.text();
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    expect(stream).toContain('"state":"input-streaming"');
    expect(stream).toContain('"state":"input-available"');
    expect(stream).toContain('"state":"output-available"');
    expect(stream).toContain('"type":"assistant-delta"');
    expect(stream).toContain('"type":"done"');
  });

  it("returns a distinct tool output-error state for the development fault", async () => {
    const response = await POST(new Request("http://localhost/api/qualify", {
      method: "POST",
      body: JSON.stringify({ ...body, demoFailure: "tool" }),
      headers: { "content-type": "application/json" },
    }));
    const stream = await response.text();
    expect(stream).toContain('"state":"output-error"');
    expect(stream).not.toContain('"type":"done"');
  });

  it("emits partial assistant text before the development stream interruption", async () => {
    const response = await POST(new Request("http://localhost/api/qualify", {
      method: "POST",
      body: JSON.stringify({ ...body, demoFailure: "mid-stream" }),
      headers: { "content-type": "application/json" },
    }));
    const stream = await response.text();
    expect(stream).toContain('"type":"assistant-delta"');
    expect(stream).toContain('"state":"output-error"');
    expect(stream).not.toContain('"type":"done"');
  });
});
