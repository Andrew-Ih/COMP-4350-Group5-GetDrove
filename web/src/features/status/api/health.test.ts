import { describe, expect, it, vi } from "vitest";

import { checkHealth } from "./health";

function respond(status: number, body: unknown): typeof fetch {
  return vi.fn(async () => new Response(JSON.stringify(body), { status }));
}

describe("checkHealth", () => {
  it("calls the service's health endpoint through the gateway", async () => {
    const fetchImpl = respond(200, { status: "ok", service: "trips" });
    await checkHealth("trips", fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith("/api/trips/health", { cache: "no-store" });
  });

  it("is up when the service answers ok", async () => {
    expect(await checkHealth("trips", respond(200, { status: "ok", service: "trips" }))).toBe("up");
  });

  it("is down when the gateway returns an error", async () => {
    expect(await checkHealth("trips", respond(502, {}))).toBe("down");
  });

  it("is down when the request fails", async () => {
    const failing = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    expect(await checkHealth("trips", failing)).toBe("down");
  });
});
