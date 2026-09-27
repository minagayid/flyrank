import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { sampleLeads } from "@/lib/data/leads";
import { LeadWorkspace } from "./lead-workspace";

describe("lead workspace recovery", () => {
  it("keeps partial streamed text and restores the question after an interruption", async () => {
    const events = [
      { type: "assistant-delta", text: "The approved budget " },
      { type: "tool-state", state: "output-error", message: "The example stream stopped." },
    ].map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(events)));

    render(<LeadWorkspace lead={sampleLeads[0]} />);
    const question = "Why did this score well?";
    fireEvent.change(screen.getByRole("textbox", { name: "Ask about this lead" }), { target: { value: question } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByText("The approved budget")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Your question is still in the box."));
    expect(screen.getByRole("textbox", { name: "Ask about this lead" })).toHaveValue(question);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
