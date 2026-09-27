import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "next/link": fileURLToPath(new URL("./tests/mocks/next-link.tsx", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: [
        "src/components/lead/lead-inbox.tsx",
        "src/components/practice/accessible-widgets.tsx",
        "src/components/practice/stateful-button.tsx",
      ],
      exclude: ["**/*.d.ts"],
      thresholds: { lines: 50, functions: 50, statements: 50, branches: 45 },
      reporter: ["text", "html"],
    },
  },
});
