import { afterEach, describe, expect, it, vi } from "vitest";

import { tripsApi } from "./clients";
import { setAccessToken } from "./session";

afterEach(() => {
  setAccessToken(undefined);
  vi.restoreAllMocks();
});

function captureRequest() {
  return vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response("[]", { headers: { "Content-Type": "application/json" } }));
}

describe("API clients and the access token", () => {
  it("send no Authorization header before logging in", async () => {
    const fetchSpy = captureRequest();
    await tripsApi.GET("/mine");
    expect((fetchSpy.mock.calls[0]?.[0] as Request).headers.get("Authorization")).toBeNull();
  });

  it("send the token as a bearer token after logging in", async () => {
    const fetchSpy = captureRequest();
    setAccessToken("abc.def.ghi");
    await tripsApi.GET("/mine");
    expect((fetchSpy.mock.calls[0]?.[0] as Request).headers.get("Authorization")).toBe("Bearer abc.def.ghi");
  });
});
