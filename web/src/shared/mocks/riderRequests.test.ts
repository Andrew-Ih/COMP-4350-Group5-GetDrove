// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as TripsPaths } from "@/shared/api/generated/trips";
import { ApiError, unwrap } from "@/shared/api/problem";

import { resetRiderRequests } from "./riderRequests";
import { server } from "./server";

const fetch = (request: Request) => globalThis.fetch(request);
const trips = createClient<TripsPaths>({ baseUrl: "http://localhost/api/trips", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  resetRiderRequests();
});
afterAll(() => server.close());

const AMIRA = "11111111-1111-4111-8111-111111111111";
const PRIYA = "22222222-2222-4222-8222-222222222222";
const DANIEL = "33333333-3333-4333-8333-333333333333";
const JORDAN = "44444444-4444-4444-8444-444444444444";
const me = { lat: 49.88, lng: -97.14 };

const detail = (tripId: string) => unwrap(trips.GET("/{trip_id}", { params: { path: { trip_id: tripId }, query: me } }));
async function ask(tripId: string, pickupId?: string) {
  const { pickups } = await detail(tripId);
  return unwrap(trips.POST("/{trip_id}/requests", { params: { path: { trip_id: tripId } }, body: { ...me, pickupId: pickupId ?? pickups[0]!.id } }));
}
const check = (id: string) => unwrap(trips.GET("/requests/{request_id}", { params: { path: { request_id: id } } }));
const cancel = (id: string) => unwrap(trips.POST("/requests/{request_id}/cancel", { params: { path: { request_id: id } } }));
const failure = (call: Promise<unknown>) => call.then(() => undefined).catch((e: unknown) => (e as ApiError).code);

describe("mock API: a rider asking for a seat", () => {
  it("sends a pending request with the chosen pickup's label and price", async () => {
    const { pickups } = await detail(PRIYA);
    const request = await ask(PRIYA, pickups[1]!.id);
    expect(request.status).toBe("pending");
    expect(request.pickup.label).toBe(pickups[1]!.label);
    expect(request.cost).toEqual(pickups[1]!.cost);
    expect((await detail(PRIYA)).myRequest?.id).toBe(request.id);
  });

  it("gets accepted on Priya's trip after a couple of checks, with the car and one seat fewer", async () => {
    const seats = (await detail(PRIYA)).trip.seatsAvailable;
    const request = await ask(PRIYA);
    expect((await check(request.id)).status).toBe("pending");
    expect((await check(request.id)).status).toBe("accepted");

    const after = await detail(PRIYA);
    expect(after.myRequest?.status).toBe("accepted");
    expect(after.vehicle?.plate).toBeTruthy();
    expect(after.trip.seatsAvailable).toBe(seats - 1);
  });

  it("gets declined on Daniel's trip, which then frees the rider to ask again", async () => {
    const request = await ask(DANIEL);
    await check(request.id);
    expect((await check(request.id)).status).toBe("declined");
    expect((await detail(DANIEL)).myRequest).toBeNull();
    expect((await ask(PRIYA)).status).toBe("pending");
  });

  it("says the last seat was taken on Amira's trip, which then shows as full", async () => {
    expect(await failure(ask(AMIRA))).toBe("trip_full");
    expect((await detail(AMIRA)).trip.seatsAvailable).toBe(0);
  });

  it("needs a card on Jordan's trip", async () => {
    expect(await failure(ask(JORDAN))).toBe("card_required");
  });

  it("refuses a second request on the same trip or at the same time", async () => {
    await ask(PRIYA);
    expect(await failure(ask(PRIYA))).toBe("already_requested");
    expect(await failure(ask(DANIEL))).toBe("overlapping_request");
  });

  it("refuses a pickup point that wasn't offered", async () => {
    expect(await failure(ask(PRIYA, "nowhere"))).toBe("pickup_not_available");
  });

  it("cancels a pending request once", async () => {
    const request = await ask(PRIYA);
    expect((await cancel(request.id)).status).toBe("cancelled");
    expect(await failure(cancel(request.id))).toBe("request_not_cancellable");
    expect((await detail(PRIYA)).myRequest).toBeNull();
  });
});
