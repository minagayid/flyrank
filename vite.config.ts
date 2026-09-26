import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(path.dirname(fileURLToPath(import.meta.url)), "src") } },
  envDir: false,
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:4000" },
  },
});
