import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LeadInbox } from "./lead-inbox";

const leads = [
  { id: "strong", name: "Ari", company: "Northline", service: "Brand", budget: "$8,000", timeline: "Six weeks", source: "Referral", status: "New", created: "Today", description: "Funded scope.", score: 82 },
  { id: "context", name: "Bo", company: "Fieldnote", service: "Web", budget: "$4,000", timeline: "Soon", source: "Web", status: "New", created: "Today", description: "Needs review.", score: 54 },
  { id: "early", name: "Cy", company: "Hushwell", service: "SEO", budget: "Unstated", timeline: "Exploring", source: "Email", status: "New", created: "Today", description: "Early project.", score: 20 },
];

describe("lead inbox", () => {
  it("shows all example requests and their score links", () => {
    render(<LeadInbox leads={leads} />);
    expect(screen.getByRole("group", { name: "Filter lead requests" })).toBeInTheDocument();
    expect(screen.getByText("3 shown")).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(3);
  });

  it("filters to one score band with pressed state", () => {
    render(<LeadInbox leads={leads} />);
    fireEvent.click(screen.getByRole("button", { name: "Strong signal" }));
    expect(screen.getByRole("button", { name: "Strong signal" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("1 shown")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Northline/ })).toHaveAttribute("href", "/leads/strong");
  });

  it("explains an empty filter and provides a reset", () => {
    render(<LeadInbox leads={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "Early / mismatch" }));
    expect(screen.getByText("No requests in this group")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show all requests" }));
    expect(screen.getByRole("button", { name: "All requests" })).toHaveAttribute("aria-pressed", "true");
  });
});
