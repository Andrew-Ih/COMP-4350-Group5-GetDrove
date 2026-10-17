// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as AccountsPaths } from "@/shared/api/generated/accounts";

import { server } from "./server";
import { mockSessionState } from "./session";

const fetch = (request: Request) => globalThis.fetch(request);
const accounts = createClient<AccountsPaths>({ baseUrl: "http://localhost/api/accounts", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  mockSessionState.logOut();
});
afterAll(() => server.close());

describe("mock API: staying logged in", () => {
  it("refreshes only after logging in, until logging out", async () => {
    expect((await accounts.POST("/auth/refresh")).response.status).toBe(401);

    await accounts.POST("/auth/login", { body: { email: "maya@myumanitoba.ca", password: "long-enough-1" } });
    const refreshed = await accounts.POST("/auth/refresh");
    expect(refreshed.data?.accessToken).toBe("mock-access-token");

    expect((await accounts.POST("/auth/logout")).response.status).toBe(204);
    expect((await accounts.POST("/auth/refresh")).response.status).toBe(401);
  });
});
