// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as TripsPaths } from "@/shared/api/generated/trips";
import { ApiError, unwrap } from "@/shared/api/problem";

import { resetPostedTrips } from "./drive";
import { DEMO_TRIP_ID, resetDriverRequests } from "./requests";
import { server } from "./server";

const fetch = (request: Request) => globalThis.fetch(request);
const trips = createClient<TripsPaths>({ baseUrl: "http://localhost/api/trips", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  resetPostedTrips();
  resetDriverRequests();
});
afterAll(() => server.close());

const list = (tripId = DEMO_TRIP_ID) => unwrap(trips.GET("/{trip_id}/requests", { params: { path: { trip_id: tripId } } }));
const accept = (id: string) => unwrap(trips.POST("/requests/{request_id}/accept", { params: { path: { request_id: id } } }));
const decline = (id: string) => unwrap(trips.POST("/requests/{request_id}/decline", { params: { path: { request_id: id } } }));
const seatsLeft = async () =>
  (await unwrap(trips.GET("/{trip_id}", { params: { path: { trip_id: DEMO_TRIP_ID } } }))).trip.seatsAvailable;
const failure = (call: Promise<unknown>) => call.then(() => undefined).catch((e: unknown) => (e as ApiError).code);

describe("mock API: a driver's requests", () => {
  it("lists the demo trip's pending requests first, then its riders in pickup order", async () => {
    const requests = await list();
    expect(requests.map((r) => r.status)).toEqual(["pending", "pending", "pending", "accepted", "accepted"]);
    expect(requests.slice(3).map((r) => r.pickupOrder)).toEqual([1, 2]);
    expect(requests[0]).not.toHaveProperty("pickup.walkSeconds"); // pickup points only
  });

  it("gives the driver their own end of the trip", async () => {
    const detail = await unwrap(trips.GET("/{trip_id}", { params: { path: { trip_id: DEMO_TRIP_ID } } }));
    expect(detail.trip.origin?.label).toBe("Wolseley Ave & Arlington St");
    expect(detail.trip.seatsAvailable).toBe(1);
  });

  it("has a detour that fails the first time and works when asked again", async () => {
    const first = (await list()).find((r) => r.rider.firstName === "Sofia")!;
    expect(first.detourSeconds).toBeNull();
    const again = (await list()).find((r) => r.rider.firstName === "Sofia")!;
    expect(again.detourSeconds).toBeGreaterThan(0);
  });

  it("accepts a request into the last seat, then refuses the next with seat_taken", async () => {
    const [first, second] = await list();
    expect((await accept(first!.id)).status).toBe("accepted");
    expect(await seatsLeft()).toBe(0);
    expect(await failure(accept(second!.id))).toBe("seat_taken");
    expect(await failure(accept(first!.id))).toBe("request_not_pending");
  });

  it("declines a request, and frees the seat of an accepted rider", async () => {
    const requests = await list();
    const pending = requests[0]!;
    const rider = requests.find((r) => r.status === "accepted")!;

    expect((await decline(pending.id)).status).toBe("declined");
    expect((await list()).map((r) => r.id)).not.toContain(pending.id);
    expect(await seatsLeft()).toBe(1);

    await decline(rider.id);
    expect(await seatsLeft()).toBe(2);
    expect(await failure(decline(pending.id))).toBe("request_not_found");
  });

  it("gives a trip posted in this session two requests along its route", async () => {
    const departureAt = new Date(Date.now() + 7 * 24 * 3600_000).toISOString();
    const place = { label: "Wolseley area", lat: 49.8794, lng: -97.1663 };
    const posted = await unwrap(trips.POST("/", { body: { direction: "to_campus", place, departureAt, seatsTotal: 3 } }));
    const requests = await list(posted.id);
    expect(requests).toHaveLength(2);
    expect(requests.every((r) => r.status === "pending" && r.detourSeconds !== null)).toBe(true);
  });

  it("refuses other drivers' trips and unknown ones", async () => {
    expect(await failure(list("22222222-2222-4222-8222-222222222222"))).toBe("not_trip_driver");
    expect(await failure(list("99999999-9999-4999-8999-999999999999"))).toBe("trip_not_found");
  });
});
