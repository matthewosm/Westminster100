import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

// Plain Vitest config — we don't need Astro's SSR pipeline for the
// logic-level tests we run here. Astro-component tests (if we add them
// later) can swap in getViteConfig from astro/config.
export default defineConfig({
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "node",
  },
});
