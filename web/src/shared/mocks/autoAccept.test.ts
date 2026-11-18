// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as TripsPaths } from "@/shared/api/generated/trips";
import { ApiError, unwrap } from "@/shared/api/problem";

import { resetAutoAcceptRules } from "./autoAccept";
import { server } from "./server";

const fetch = (request: Request) => globalThis.fetch(request);
const trips = createClient<TripsPaths>({ baseUrl: "http://localhost/api/trips", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  resetAutoAcceptRules();
});
afterAll(() => server.close());

const get = () => unwrap(trips.GET("/auto-accept"));
const put = (body: { enabled: boolean; maxDetourMinutes: number; minRating: number | null }) => unwrap(trips.PUT("/auto-accept", { body }));

describe("mock API: auto-accept rules", () => {
  it("starts with the contract's defaults", async () => {
    expect(await get()).toEqual({ enabled: false, maxDetourMinutes: 5, minRating: null });
  });

  it("saves rules and returns them after", async () => {
    const saved = { enabled: true, maxDetourMinutes: 8, minRating: 4 };
    expect(await put(saved)).toEqual(saved);
    expect(await get()).toEqual(saved);
  });

  it.each([
    [{ enabled: true, maxDetourMinutes: 31, minRating: null }, "maxDetourMinutes"],
    [{ enabled: true, maxDetourMinutes: 2.5, minRating: null }, "maxDetourMinutes"],
    [{ enabled: true, maxDetourMinutes: 5, minRating: 0.5 }, "minRating"],
  ])("rejects %j", async (body, field) => {
    const error = await put(body).catch((e: unknown) => e);
    expect((error as ApiError).code).toBe("invalid_input");
    expect((error as ApiError).problem.errors?.[0]?.field).toBe(field);
  });
});
