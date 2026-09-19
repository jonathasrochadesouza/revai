import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/lib/**", "src/components/**"],
      // Gate only the contract-bearing module for now; `api.ts` (SSE reader
      // loops) and the static model catalogue are e2e territory until the
      // Playwright suite exists — see the tracking issue.
      thresholds: {
        "src/lib/errors.ts": { statements: 85, branches: 80, functions: 90, lines: 85 },
      },
    },
  },
});
