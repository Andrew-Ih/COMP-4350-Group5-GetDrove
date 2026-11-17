// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as RoutingPaths } from "@/shared/api/generated/routing";
import type { paths as TripsPaths } from "@/shared/api/generated/trips";
import { ApiError, unwrap } from "@/shared/api/problem";

import { resetPostedTrips } from "./drive";
import { server } from "./server";

const fetch = (request: Request) => globalThis.fetch(request);
const trips = createClient<TripsPaths>({ baseUrl: "http://localhost/api/trips", fetch });
const routing = createClient<RoutingPaths>({ baseUrl: "http://localhost/api/routing", fetch });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  resetPostedTrips();
});
afterAll(() => server.close());

const place = { label: "Wolseley area", lat: 49.8794, lng: -97.1663 };
const inAWeek = (minute: number) => {
  const date = new Date(Date.now() + 7 * 24 * 3600_000);
  date.setUTCMinutes(minute, 0, 0);
  return date.toISOString();
};
const postTrip = (departureAt: string, direction: "to_campus" | "from_campus" = "to_campus") =>
  unwrap(trips.POST("/", { body: { direction, place, departureAt, seatsTotal: 3 } }));

describe("mock API: posting a trip", () => {
  it("returns the trip with its route worked out, and the driver's own end", async () => {
    const departureAt = inAWeek(10);
    const trip = await postTrip(departureAt);

    expect(trip.departureAt).toBe(departureAt);
    expect(trip.origin).toEqual(place);
    expect(trip.destination?.label).toBe("University Centre");
    expect(trip.seatsAvailable).toBe(3);
    expect(trip.durationSeconds).toBeGreaterThan(0);
    expect(Date.parse(trip.estimatedArrivalAt)).toBe(Date.parse(departureAt) + trip.durationSeconds * 1000);

    const route = await unwrap(routing.GET("/trips/{trip_id}/geometry", { params: { path: { trip_id: trip.id } } }));
    expect(route.geometry.coordinates[0]).toEqual([place.lng, place.lat]);
  });

  it("starts at campus for a trip from campus", async () => {
    const trip = await postTrip(inAWeek(10), "from_campus");
    expect(trip.origin?.label).toBe("University Centre");
    expect(trip.destination).toEqual(place);
  });

  it("lists posted trips as the driver's upcoming trips", async () => {
    const later = await postTrip(inAWeek(40));
    const sooner = await postTrip(inAWeek(10));

    const mine = await unwrap(trips.GET("/mine", { params: { query: { role: "driver" } } }));
    const postedHere = mine.filter((t) => t.id === sooner.id || t.id === later.id);
    expect(postedHere.map((t) => t.id)).toEqual([sooner.id, later.id]);
  });

  it("refuses a departure in the past, and is unavailable for :55", async () => {
    const past = await postTrip("2020-01-01T13:00:00Z").catch((e: unknown) => e);
    expect((past as ApiError).code).toBe("departure_in_past");
    const unavailable = await postTrip(inAWeek(55)).catch((e: unknown) => e);
    expect((unavailable as ApiError).code).toBe("routing_unavailable");
  });
});

describe("mock API: My trips", () => {
  const mine = (when: "upcoming" | "past") => unwrap(trips.GET("/mine", { params: { query: { when } } }));
  const failure = (call: Promise<unknown>) => call.then(() => undefined).catch((e: unknown) => (e as ApiError).code);

  it("lists upcoming trips soonest first, cancelled ones included, and past ones separately", async () => {
    const upcoming = await mine("upcoming");
    expect(upcoming.length).toBeGreaterThan(0);
    expect(upcoming.some((t) => t.status === "cancelled")).toBe(true);
    expect(upcoming.some((t) => t.seriesId)).toBe(true);
    const departures = upcoming.map((t) => Date.parse(t.departureAt));
    expect(departures).toEqual([...departures].sort((a, b) => a - b));

    const past = await mine("past");
    expect(past.length).toBeGreaterThan(0);
    expect(past.every((t) => Date.parse(t.departureAt) < Date.now())).toBe(true);
  });

  it("cancels one trip, and refuses to cancel it again", async () => {
    const trip = (await mine("upcoming")).find((t) => t.status === "scheduled" && !t.seriesId)!;
    const cancelled = await unwrap(trips.POST("/{trip_id}/cancel", { params: { path: { trip_id: trip.id } } }));
    expect(cancelled.status).toBe("cancelled");
    expect((await mine("upcoming")).find((t) => t.id === trip.id)?.status).toBe("cancelled");
    expect(await failure(unwrap(trips.POST("/{trip_id}/cancel", { params: { path: { trip_id: trip.id } } })))).toBe(
      "trip_not_cancellable",
    );
  });

  it("cancels every trip in a series", async () => {
    const seriesId = (await mine("upcoming")).find((t) => t.seriesId)!.seriesId!;
    const cancelled = await unwrap(trips.POST("/series/{series_id}/cancel", { params: { path: { series_id: seriesId } } }));
    expect(cancelled.length).toBeGreaterThan(1);
    expect((await mine("upcoming")).filter((t) => t.seriesId === seriesId).every((t) => t.status === "cancelled")).toBe(true);
  });

  it("lists the rider's upcoming and past rides with their requests", async () => {
    const upcoming = await unwrap(trips.GET("/requests/mine", { params: { query: { when: "upcoming" } } }));
    expect(upcoming.map((r) => r.request.status)).toEqual(expect.arrayContaining(["pending", "accepted", "declined"]));
    expect(upcoming.every((r) => r.trip.origin === null)).toBe(true); // the driver's end stays private
    const past = await unwrap(trips.GET("/requests/mine", { params: { query: { when: "past" } } }));
    expect(past[0]?.trip.status).toBe("completed");
  });
});
