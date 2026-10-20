import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    // A simulated browser, so component tests can render and click.
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // Absolute API URLs in tests: Node's fetch can't resolve "/api/..." without a page.
    env: { NEXT_PUBLIC_API_BASE_URL: "http://localhost/api" },
    // npm run test:coverage (docs/testing/testing-strategy.md). Reports go to web/coverage/.
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/**/*.d.ts",
        "src/shared/testing/**", // test helpers
        "src/shared/mocks/**", // the mock API (demo data for dev:mock and tests)
        "src/shared/api/generated/**", // types generated from the contracts
      ],
      reporter: ["text", "html", "json-summary"],
    },
  },
});
