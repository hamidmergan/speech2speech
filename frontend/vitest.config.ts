import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Unit tests for the frontend, scoped to src/. Component and hook tests ask for
// the jsdom environment with a docblock of their own.
export default defineConfig({
  // The React 19 JSX runtime, the same one Next.js compiles the app with.
  esbuild: { jsx: "automatic" },
  // Mirrors the "@/*" path in tsconfig.json. Without it a tested module cannot
  // reach a shared helper under src/lib the way the app does.
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
    // One copy of each, otherwise a provider in a helper module and a hook in a
    // component end up on two different React contexts.
    dedupe: ["react", "react-dom", "next-intl", "use-intl"],
  },
  test: {
    environment: "node",
    // next-intl ships ESM that imports "next/navigation" without a file
    // extension. Node only resolves that if Vite transpiles the package too.
    server: { deps: { inline: [/next-intl/] } },
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["node_modules", ".next"],
    coverage: {
      // v8 instrumentation (no Babel), matches the vitest 2.x line.
      provider: "v8",
      // `all: true` counts every source file, not just the ones a test
      // imports, so the number reflects the whole codebase honestly. Most of
      // src/ is UI without unit tests, so expect a low baseline.
      all: true,
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/**/*.d.ts",
        "src/**/types.ts",
        "src/**/_types.ts",
      ],
      // text-summary keeps the CI log short; json-summary feeds the CI job
      // summary; html/json land as artifacts.
      reporter: ["text-summary", "json", "json-summary", "html"],
    },
  },
});
