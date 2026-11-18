import { delay, http, HttpResponse } from "msw";

import type { components as Trips } from "@/shared/api/generated/trips";

/**
 * Mock API for the driver's auto-accept rules (#45), matching GET and PUT
 * /api/trips/auto-accept. Starts with the contract's defaults (off, 5 minutes, any
 * rating) and checks the same limits.
 */

type Rules = Trips["schemas"]["AutoAcceptRules"];

const DEFAULTS: Rules = { enabled: false, maxDetourMinutes: 5, minRating: null };
let rules: Rules = { ...DEFAULTS };

/** Back to the defaults (for tests). */
export function resetAutoAcceptRules() {
  rules = { ...DEFAULTS };
}

const invalid = (field: string, message: string) =>
  HttpResponse.json(
    {
      type: "about:blank",
      title: "Invalid input",
      status: 422,
      detail: "Invalid input",
      instance: "/api/trips/auto-accept",
      code: "invalid_input",
      requestId: "mock",
      errors: [{ field, message }],
    },
    { status: 422, headers: { "Content-Type": "application/problem+json" } },
  );

export const autoAcceptHandlers = [
  http.get("*/api/trips/auto-accept", async () => {
    await delay();
    return HttpResponse.json(rules);
  }),

  http.put("*/api/trips/auto-accept", async ({ request }) => {
    const body = (await request.json()) as Rules;
    await delay();
    if (typeof body.enabled !== "boolean") return invalid("enabled", "Must be true or false");
    if (!Number.isInteger(body.maxDetourMinutes) || body.maxDetourMinutes < 0 || body.maxDetourMinutes > 30) {
      return invalid("maxDetourMinutes", "Must be a whole number from 0 to 30");
    }
    if (body.minRating !== null && (typeof body.minRating !== "number" || body.minRating < 1 || body.minRating > 5)) {
      return invalid("minRating", "Must be from 1 to 5, or null");
    }
    rules = { enabled: body.enabled, maxDetourMinutes: body.maxDetourMinutes, minRating: body.minRating };
    return HttpResponse.json(rules);
  }),
];
