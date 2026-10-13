import { delay, http, HttpResponse } from "msw";

import type { components as Accounts } from "@/shared/api/generated/accounts";
import type { components as Trips } from "@/shared/api/generated/trips";

import { maya, myTrips, searchResults } from "./data";

type Problem = Accounts["schemas"]["Problem"];

function problem(status: number, code: string, detail: string, instance: string, extra: Partial<Problem> = {}) {
  const body: Problem = { type: "about:blank", title: detail, status, detail, instance, code, requestId: "mock", ...extra };
  return HttpResponse.json(body, { status, headers: { "Content-Type": "application/problem+json" } });
}

/**
 * Fake responses for the Sprint 1 endpoints, matching contracts/openapi. Turned on with
 * NEXT_PUBLIC_API_MOCKING=enabled, so pages can be built before the real endpoints exist.
 *
 * Special inputs to try the error states:
 *   - signup with an email not ending in @myumanitoba.ca → 422 email_not_uofm
 *   - signup with taken@myumanitoba.ca                    → 409 email_taken
 *   - login with password "wrong"                         → 401 invalid_credentials
 *   - login with unverified@myumanitoba.ca                → 403 email_not_verified
 */
export const handlers = [
  http.post("*/api/accounts/auth/signup", async ({ request }) => {
    const body = (await request.json()) as Accounts["schemas"]["SignupRequest"];
    await delay(); // realistic in the browser, none in tests
    const instance = "/api/accounts/auth/signup";
    if (!body.email.toLowerCase().endsWith("@myumanitoba.ca")) {
      return problem(422, "email_not_uofm", "Only @myumanitoba.ca emails can sign up", instance, {
        errors: [{ field: "email", message: "Use your @myumanitoba.ca email" }],
      });
    }
    if (body.email.toLowerCase() === "taken@myumanitoba.ca") {
      return problem(409, "email_taken", "An account with this email already exists", instance);
    }
    const created: Accounts["schemas"]["SignupResponse"] = {
      id: crypto.randomUUID(),
      email: body.email,
      emailVerified: false,
    };
    return HttpResponse.json(created, { status: 201 });
  }),

  http.post("*/api/accounts/auth/login", async ({ request }) => {
    const body = (await request.json()) as Accounts["schemas"]["LoginRequest"];
    await delay(); // realistic in the browser, none in tests
    const instance = "/api/accounts/auth/login";
    if (body.password === "wrong") {
      return problem(401, "invalid_credentials", "Wrong email or password", instance);
    }
    if (body.email.toLowerCase() === "unverified@myumanitoba.ca") {
      return problem(403, "email_not_verified", "Verify your email before logging in", instance);
    }
    const token: Accounts["schemas"]["TokenResponse"] = {
      accessToken: "mock-access-token",
      tokenType: "Bearer",
      expiresIn: 900,
    };
    return HttpResponse.json(token);
  }),

  http.get("*/api/accounts/me", () => HttpResponse.json(maya)),

  http.get("*/api/trips/search", async () => {
    await delay(); // realistic in the browser, none in tests
    return HttpResponse.json(searchResults);
  }),

  http.get("*/api/trips/mine", () => HttpResponse.json(myTrips)),

  http.post("*/api/trips/", async ({ request }) => {
    const body = (await request.json()) as Trips["schemas"]["PostTripRequest"];
    await delay(); // realistic in the browser, none in tests
    const created: Trips["schemas"]["Trip"] = {
      ...myTrips[0]!,
      id: crypto.randomUUID(),
      direction: body.direction,
      departureAt: body.departureAt,
      seatsTotal: body.seatsTotal,
      seatsAvailable: body.seatsTotal,
    };
    return HttpResponse.json(created, { status: 201 });
  }),
];
