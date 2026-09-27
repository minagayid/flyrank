import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StatefulButton } from "./stateful-button";

describe("stateful button", () => {
  it("announces loading then success", async () => {
    const action = vi.fn().mockResolvedValue(undefined);
    render(<StatefulButton action={action} />);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("button", { name: "Cancel working" })).toHaveAttribute("aria-busy", "true");
    await waitFor(() => expect(screen.getByRole("button", { name: "Done" })).toHaveAttribute("aria-busy", "false"));
    expect(screen.getByRole("status")).toHaveTextContent("Done.");
  });

  it("cancels an in-flight action", async () => {
    let capturedSignal: AbortSignal | undefined;
    const action = vi.fn((signal: AbortSignal) => {
      capturedSignal = signal;
      return new Promise<void>((_resolve, reject) => signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError"))));
    });
    render(<StatefulButton action={action} />);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel working" }));
    await waitFor(() => expect(capturedSignal?.aborted).toBe(true));
    expect(screen.getByRole("status")).toHaveTextContent("Action cancelled");
  });

  it("shows a recoverable error state", async () => {
    const action = vi.fn().mockRejectedValue(new Error("local failure"));
    render(<StatefulButton action={action} />);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("You can try again");
  });

  it("does not run when disabled", () => {
    const action = vi.fn();
    render(<StatefulButton action={action} disabled />);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(action).not.toHaveBeenCalled();
  });
});
