// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as RoutingPaths } from "@/shared/api/generated/routing";
import { ApiError, unwrap } from "@/shared/api/problem";

import { server } from "./server";

const fetch = (request: Request) => globalThis.fetch(request);
const routing = createClient<RoutingPaths>({ baseUrl: "http://localhost/api/routing", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("mock API: finding a place by its address", () => {
  it("finds the places matching every word typed", async () => {
    const { places } = await unwrap(routing.POST("/places", { body: { query: "750 osborne" } }));
    expect(places.map((p) => p.label)).toEqual(["750 Osborne Street, Fort Rouge"]);
  });

  it("finds nothing for anything else", async () => {
    expect(await unwrap(routing.POST("/places", { body: { query: "123 Nowhere Rd" } }))).toEqual({ places: [] });
  });

  it("answers 503 geocoding_unavailable for 'slow lookup'", async () => {
    const failed = unwrap(routing.POST("/places", { body: { query: "slow lookup" } }));
    await expect(failed).rejects.toBeInstanceOf(ApiError);
    await expect(failed).rejects.toMatchObject({ code: "geocoding_unavailable" });
  });
});
