import { expect, test } from "@playwright/test";

// A demo rider from infra/seed/demo.json (Priya, on Maya's route), seeded on the live site.
const email = process.env.SMOKE_EMAIL ?? "getdrove.demo.priya@myumanitoba.ca";
const password = process.env.SMOKE_PASSWORD;

/** The next weekday after today, at 13:00 UTC (8 AM in Winnipeg), as the search's ISO time. */
function nextWeekdayMorning(now = new Date()): string {
  const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 13));
  while (day.getUTCDay() === 0 || day.getUTCDay() === 6) day.setUTCDate(day.getUTCDate() + 1);
  return day.toISOString();
}

test("a demo rider can log in and search for a ride to campus", async ({ page }) => {
  if (!password) throw new Error("Set SMOKE_PASSWORD to the demo accounts' password (DEMO_ACCOUNT_PASSWORD).");

  await page.goto("/login");
  await page.getByLabel("UofM email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/ride(\?|$)/);

  // From Osborne Village to campus. Whether trips come back depends on when the seed last
  // ran, so this checks the search works (the results heading shows), not the number.
  const search = new URLSearchParams({ lat: "49.87680", lng: "-97.14380", direction: "to_campus", time: nextWeekdayMorning() });
  await page.goto(`/ride/results?${search}`);

  const heading = page.getByRole("heading", { level: 1, name: /^(No trips|\d+ trips?) / });
  await expect(heading).toBeVisible({ timeout: 30_000 });
  console.log(`Search answered: ${await heading.textContent()}`);
});
