import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { tripsApi } from "./clients";
import { endSession, getAccessToken, logOut, refreshSession, setAccessToken, startSession } from "./session";

type Answer = { status: number; body?: unknown };

/** Fake fetch that answers by path; records each call's path, method and Authorization. */
function fakeApi(routes: Record<string, Answer | Answer[]>) {
  const queues = Object.fromEntries(Object.entries(routes).map(([k, v]) => [k, Array.isArray(v) ? [...v] : v]));
  const calls: { path: string; method: string; auth: string | null }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(new URL(String(input), "http://localhost"), init);
    const path = new URL(request.url).pathname;
    calls.push({ path, method: request.method, auth: request.headers.get("Authorization") });
    const key = Object.keys(queues).find((k) => path.endsWith(k));
    const entry = key ? queues[key] : undefined;
    const answer = (Array.isArray(entry) ? entry.shift() : entry) ?? { status: 500 };
    const body = answer.body === undefined ? null : JSON.stringify(answer.body);
    return new Response(body, { status: answer.status, headers: { "Content-Type": "application/json" } });
  });
  return calls;
}

const TOKEN = { accessToken: "new-token", tokenType: "Bearer", expiresIn: 900 };
const EXPIRED = { status: 401, body: { status: 401, code: "invalid_refresh_token", detail: "Log in again." } };

beforeEach(() => endSession());
afterEach(() => {
  endSession();
  vi.useRealTimers();
  vi.restoreAllMocks();
  Reflect.deleteProperty(navigator, "locks");
});

describe("API clients and the access token", () => {
  it("send no Authorization header before logging in", async () => {
    const calls = fakeApi({ "/trips/mine": { status: 200, body: [] } });
    await tripsApi.GET("/mine");
    expect(calls[0]?.auth).toBeNull();
  });

  it("send the token as a bearer token after logging in", async () => {
    const calls = fakeApi({ "/trips/mine": { status: 200, body: [] } });
    setAccessToken("abc.def.ghi");
    await tripsApi.GET("/mine");
    expect(calls[0]?.auth).toBe("Bearer abc.def.ghi");
  });

  it("refresh once and try again when the token has expired", async () => {
    const calls = fakeApi({
      "/trips/mine": [{ status: 401 }, { status: 200, body: [] }],
      "/auth/refresh": { status: 200, body: TOKEN },
    });
    setAccessToken("old-token");

    const { data, response } = await tripsApi.GET("/mine");

    expect(response.status).toBe(200);
    expect(data).toEqual([]);
    expect(calls.map((c) => c.path)).toEqual(["/api/trips/mine", "/api/accounts/auth/refresh", "/api/trips/mine"]);
    expect(calls[2]?.auth).toBe("Bearer new-token");
  });

  it("give up (keeping the 401) when the session can't be refreshed", async () => {
    const calls = fakeApi({ "/trips/mine": { status: 401 }, "/auth/refresh": EXPIRED });
    setAccessToken("old-token");

    const { response } = await tripsApi.GET("/mine");

    expect(response.status).toBe(401);
    expect(calls).toHaveLength(2); // no second try
    expect(getAccessToken()).toBeUndefined();
  });

  it("never retry a 401 without a token", async () => {
    const calls = fakeApi({ "/trips/mine": { status: 401 } });
    await tripsApi.GET("/mine");
    expect(calls).toHaveLength(1);
  });
});

describe("refreshSession", () => {
  it("keeps the new token and says the student is logged in", async () => {
    fakeApi({ "/auth/refresh": { status: 200, body: TOKEN } });
    expect(await refreshSession()).toBe(true);
    expect(getAccessToken()).toBe("new-token");
  });

  it("forgets the session when the cookie no longer works", async () => {
    fakeApi({ "/auth/refresh": EXPIRED });
    setAccessToken("old-token");
    expect(await refreshSession()).toBe(false);
    expect(getAccessToken()).toBeUndefined();
  });

  it("keeps the session when the network fails, to try again later", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"));
    setAccessToken("old-token");
    expect(await refreshSession()).toBe(false);
    expect(getAccessToken()).toBe("old-token");
  });

  it("sends one request however many callers ask at once", async () => {
    const calls = fakeApi({ "/auth/refresh": { status: 200, body: TOKEN } });
    const results = await Promise.all([refreshSession(), refreshSession(), refreshSession()]);
    expect(results).toEqual([true, true, true]);
    expect(calls).toHaveLength(1);
  });

  it("takes the browser's lock, so tabs refresh one at a time", async () => {
    const request = vi.fn((_name: string, callback: () => Promise<boolean>) => callback());
    Object.defineProperty(navigator, "locks", { value: { request }, configurable: true });
    fakeApi({ "/auth/refresh": { status: 200, body: TOKEN } });

    expect(await refreshSession()).toBe(true);
    expect(request).toHaveBeenCalledWith("getdrove-session-refresh", expect.any(Function));
  });

  it("happens a minute before the token expires", async () => {
    vi.useFakeTimers();
    const calls = fakeApi({ "/auth/refresh": { status: 200, body: TOKEN } });
    startSession({ accessToken: "first", expiresIn: 900 });

    await vi.advanceTimersByTimeAsync(838_000);
    expect(calls).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(3_000);
    expect(calls.map((c) => c.path)).toEqual(["/api/accounts/auth/refresh"]);
    expect(getAccessToken()).toBe("new-token");
  });
});

describe("logOut", () => {
  it("ends the session on the server and here", async () => {
    const calls = fakeApi({ "/auth/logout": { status: 204 } });
    setAccessToken("tok");

    await logOut();

    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(["POST /api/accounts/auth/logout"]);
    expect(getAccessToken()).toBeUndefined();
  });

  it("still forgets the session when offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"));
    setAccessToken("tok");
    await logOut();
    expect(getAccessToken()).toBeUndefined();
  });
});
