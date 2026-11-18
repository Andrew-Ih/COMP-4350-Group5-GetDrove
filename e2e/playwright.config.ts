import { defineConfig, devices } from "@playwright/test";

/**
 * Smoke tests against a running GetDrove (#177): the live site after a deploy, or any
 * address in SMOKE_BASE_URL. They click through the real app in Chromium, like a student.
 */
export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  // One retry, so a slow first page load right after a restart doesn't fail the deploy.
  retries: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.SMOKE_BASE_URL ?? "https://getdrove.duckdns.org",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    // Browser tests against the site: npm run smoke
    { name: "chromium", testMatch: "*.smoke.ts", use: { ...devices["Desktop Chrome"] } },
    // Plain checks of the helpers, no browser or site: npm test
    { name: "unit", testMatch: "*.test.ts" },
  ],
});
