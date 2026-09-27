import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

Object.defineProperty(HTMLElement.prototype, "getClientRects", {
  configurable: true,
  value: () => [{ width: 10, height: 10 }],
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
