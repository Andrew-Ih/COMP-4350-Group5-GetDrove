import { delay, http, HttpResponse } from "msw";

import type { components as Accounts } from "@/shared/api/generated/accounts";
import type { components as Routing } from "@/shared/api/generated/routing";

import { maya, myTrips, searchResultsFor } from "./data";
import { driveHandlers } from "./drive";

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
 *   - /verify?token=expired                               → 410 token_expired
 *   - /verify?token=used                                  → 400 invalid_token
 *   - any other token                                     → verified
 *   - a search for a time ending in :05                   → no trips
 *   - a search for a time ending in :55                   → 503 routing_unavailable
 */

// Routes of the trips from the latest search, for the map.
const routes = new Map<string, Routing["schemas"]["RouteFeature"]>();
export const handlers = [
  ...driveHandlers, // posting a trip (#96): see drive.ts
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

  http.post("*/api/accounts/auth/verify", async ({ request }) => {
    const { token } = (await request.json()) as Accounts["schemas"]["VerifyEmailRequest"];
    await delay();
    const instance = "/api/accounts/auth/verify";
    if (token === "expired") {
      return problem(410, "token_expired", "This link has expired", instance);
    }
    if (token === "used") {
      return problem(400, "invalid_token", "This link is not valid", instance);
    }
    return new HttpResponse(null, { status: 204 });
  }),

  http.post("*/api/accounts/auth/resend-verification", async () => {
    await delay();
    return HttpResponse.json(null, { status: 202 });
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

  http.get("*/api/trips/search", async ({ request }) => {
    const params = new URL(request.url).searchParams;
    const query = {
      lat: Number(params.get("lat")),
      lng: Number(params.get("lng")),
      direction: params.get("direction") === "from_campus" ? ("from_campus" as const) : ("to_campus" as const),
      time: params.get("time") ?? "",
    };
    await delay(); // realistic in the browser, none in tests
    const instance = "/api/trips/search";
    const time = new Date(query.time);
    if (!params.get("lat") || !params.get("lng") || Number.isNaN(time.getTime())) {
      return problem(422, "invalid_input", "Invalid input", instance);
    }
    if (time.getUTCMinutes() === 55) {
      return problem(503, "routing_unavailable", "Matching is unavailable right now", instance);
    }
    if (time.getUTCMinutes() === 5) {
      return HttpResponse.json([]);
    }
    const found = searchResultsFor(query);
    for (const [id, route] of found.routes) routes.set(id, route);
    return HttpResponse.json(found.results);
  }),

  http.get("*/api/routing/trips/:tripId/geometry", ({ params }) => {
    const route = routes.get(String(params.tripId));
    return route
      ? HttpResponse.json(route)
      : problem(404, "route_not_found", "No route for this trip", `/api/routing/trips/${String(params.tripId)}/geometry`);
  }),

  http.get("*/api/trips/mine", () => HttpResponse.json(myTrips)),
];
