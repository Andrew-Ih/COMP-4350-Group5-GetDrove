// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as AccountsPaths } from "@/shared/api/generated/accounts";
import type { paths as TripsPaths } from "@/shared/api/generated/trips";
import { ApiError, unwrap } from "@/shared/api/problem";

import { server } from "./server";

// Absolute URLs: Node has no page origin to resolve "/api/..." against. fetch is looked
// up per request, so it's the one MSW replaces in server.listen().
const fetch = (request: Request) => globalThis.fetch(request);
const accounts = createClient<AccountsPaths>({ baseUrl: "http://localhost/api/accounts", fetch });
const trips = createClient<TripsPaths>({ baseUrl: "http://localhost/api/trips", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const signup = (email: string) =>
  unwrap(accounts.POST("/auth/signup", { body: { email, password: "long-enough-1", firstName: "Maya", lastName: "Singh" } }));

describe("mock API", () => {
  it("signs up a UofM email", async () => {
    const user = await signup("maya@myumanitoba.ca");
    expect(user.emailVerified).toBe(false);
  });

  it("rejects other emails with email_not_uofm", async () => {
    const error = await signup("maya@gmail.com").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("email_not_uofm");
    expect((error as ApiError).problem.errors?.[0]?.field).toBe("email");
  });

  it("rejects a taken email with email_taken", async () => {
    const error = await signup("taken@myumanitoba.ca").catch((e: unknown) => e);
    expect((error as ApiError).status).toBe(409);
  });

  it("returns search results with a pickup and cost", async () => {
    const results = await unwrap(
      trips.GET("/search", {
        params: { query: { lat: 49.88, lng: -97.14, direction: "to_campus", time: "2026-10-20T13:30:00Z" } },
      }),
    );
    expect(results.length).toBeGreaterThan(0);
    expect(results[0]?.cost?.currency).toBe("CAD");
  });
});
