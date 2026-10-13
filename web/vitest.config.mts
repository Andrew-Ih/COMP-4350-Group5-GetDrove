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
  },
});
