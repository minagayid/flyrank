import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import AccessibleWidgets from "./accessible-widgets";

describe("accessible widgets", () => {
  it("opens the dialog, focuses its title, closes with Escape, and restores focus", async () => {
    const user = userEvent.setup();
    render(<AccessibleWidgets />);
    const trigger = screen.getByRole("button", { name: "Open sample dialog" });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog");
    await waitFor(() => expect(screen.getByRole("heading", { name: "Save this lead as a priority?" })).toHaveFocus());
    await user.keyboard("{Escape}");
    expect(dialog).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("traps focus between the first and last controls", async () => {
    const user = userEvent.setup();
    render(<AccessibleWidgets />);
    await user.click(screen.getByRole("button", { name: "Open sample dialog" }));
    const close = screen.getByRole("button", { name: "Close dialog" });
    const confirm = screen.getByRole("button", { name: "Confirm sample" });
    close.focus();
    await user.tab();
    expect(screen.getByRole("textbox", { name: "Add a review note" })).toHaveFocus();
    confirm.focus();
    await user.tab();
    expect(close).toHaveFocus();
  });

  it("uses arrow keys to select tabs and exposes only the active panel", async () => {
    render(<AccessibleWidgets />);
    const overview = screen.getByRole("tab", { name: "Overview" });
    overview.focus();
    fireEvent.keyDown(overview, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Evidence" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Evidence" })).toBeVisible();
    fireEvent.keyDown(screen.getByRole("tab", { name: "Evidence" }), { key: "End" });
    expect(screen.getByRole("tab", { name: "History" })).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(screen.getByRole("tab", { name: "History" }), { key: "Home" });
    expect(overview).toHaveAttribute("aria-selected", "true");
  });

  it("toggles a disclosure and synchronizes its accessible state", async () => {
    const user = userEvent.setup();
    render(<AccessibleWidgets />);
    const trigger = screen.getByRole("button", { name: "What makes this disclosure accessible?" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region", { name: "What makes this disclosure accessible?" })).toBeVisible();
    await user.keyboard(" ");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
