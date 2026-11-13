// @vitest-environment node

import createClient from "openapi-fetch";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { paths as AccountsPaths } from "@/shared/api/generated/accounts";
import type { paths as RoutingPaths } from "@/shared/api/generated/routing";
import type { paths as TripsPaths } from "@/shared/api/generated/trips";
import { ApiError, unwrap } from "@/shared/api/problem";

import { server } from "./server";

// Absolute URLs: Node has no page origin to resolve "/api/..." against. fetch is looked
// up per request, so it's the one MSW replaces in server.listen().
const fetch = (request: Request) => globalThis.fetch(request);
const accounts = createClient<AccountsPaths>({ baseUrl: "http://localhost/api/accounts", fetch });
const trips = createClient<TripsPaths>({ baseUrl: "http://localhost/api/trips", fetch });
const routing = createClient<RoutingPaths>({ baseUrl: "http://localhost/api/routing", fetch });

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

  const search = (time: string, direction: "to_campus" | "from_campus" = "to_campus") =>
    unwrap(trips.GET("/search", { params: { query: { lat: 49.88, lng: -97.14, direction, time } } }));

  it("returns search results with a pickup and cost, soonest first", async () => {
    const results = await search("2026-10-20T13:30:00Z");
    expect(results.length).toBeGreaterThan(0);
    expect(results[0]?.cost?.currency).toBe("CAD");
    const departures = results.map((r) => Date.parse(r.trip.departureAt));
    expect(departures).toEqual([...departures].sort((a, b) => a - b));
  });

  it("fits the contract's time window and keeps the driver's end private", async () => {
    const arriveBy = Date.parse("2026-10-20T13:30:00Z");
    for (const { trip } of await search("2026-10-20T13:30:00Z")) {
      const arrival = Date.parse(trip.estimatedArrivalAt);
      expect(arrival).toBeLessThanOrEqual(arriveBy);
      expect(arrival).toBeGreaterThanOrEqual(arriveBy - 60 * 60_000);
      expect(trip.origin).toBeNull();
    }
    const leaveAfter = Date.parse("2026-10-20T21:30:00Z");
    for (const { trip } of await search("2026-10-20T21:30:00Z", "from_campus")) {
      expect(Date.parse(trip.departureAt)).toBeGreaterThanOrEqual(leaveAfter);
      expect(Date.parse(trip.departureAt)).toBeLessThanOrEqual(leaveAfter + 60 * 60_000);
      expect(trip.destination).toBeNull();
    }
  });

  it("returns no trips for a time ending in :05, and 503 for :55", async () => {
    expect(await search("2026-10-20T13:05:00Z")).toEqual([]);
    const error = await search("2026-10-20T13:55:00Z").catch((e: unknown) => e);
    expect((error as ApiError).code).toBe("routing_unavailable");
  });

  it("puts each pickup on its own trip's route, a short walk from the rider", async () => {
    const results = await search("2026-10-20T13:30:00Z");
    for (const { trip, pickup } of results) {
      const route = await unwrap(routing.GET("/trips/{trip_id}/geometry", { params: { path: { trip_id: trip.id } } }));
      expect(route.geometry.coordinates).toContainEqual([pickup.lng, pickup.lat]);
      expect(Math.abs(pickup.lat - 49.88)).toBeLessThan(0.01); // within about 1 km
      expect(Math.abs(pickup.lng + 97.14)).toBeLessThan(0.015);
    }
  });

  it("returns the route of a trip from the latest search", async () => {
    const [first] = await search("2026-10-20T13:30:00Z");
    const route = await unwrap(routing.GET("/trips/{trip_id}/geometry", { params: { path: { trip_id: first!.trip.id } } }));
    expect(route.properties.tripId).toBe(first!.trip.id);
    expect(route.geometry.coordinates.length).toBeGreaterThan(1);

    const missing = await unwrap(
      routing.GET("/trips/{trip_id}/geometry", { params: { path: { trip_id: "99999999-9999-4999-8999-999999999999" } } }),
    ).catch((e: unknown) => e);
    expect((missing as ApiError).code).toBe("route_not_found");
  });

  const tripDetail = (tripId: string, query?: { lat?: number; lng?: number }) =>
    unwrap(trips.GET("/{trip_id}", { params: { path: { trip_id: tripId }, query } }));

  it("returns a trip from the search with 3 pickup points on its route, the search's one first", async () => {
    const [first] = await search("2026-10-20T13:30:00Z");
    const detail = await tripDetail(first!.trip.id, { lat: 49.88, lng: -97.14 });

    expect(detail.trip).toEqual(first!.trip);
    expect(detail.pickups).toHaveLength(3);
    expect(detail.pickups[0]).toMatchObject({ label: first!.pickup.label, walkSeconds: first!.pickup.walkSeconds, cost: first!.cost });
    expect(new Set(detail.pickups.map((p) => p.id)).size).toBe(3);
    expect(detail.myRequest).toBeNull();
    expect(detail.vehicle).toBeNull(); // only for accepted riders

    // Every point lies on the trip's route: on the line between two of its corners.
    const route = await unwrap(routing.GET("/trips/{trip_id}/geometry", { params: { path: { trip_id: first!.trip.id } } }));
    const corners = route.geometry.coordinates;
    for (const p of detail.pickups) {
      const onRoute = corners.slice(1).some(([lng2, lat2], i) => {
        const [lng1, lat1] = corners[i]!;
        const cross = (lng2! - lng1!) * (p.lat - lat1!) - (lat2! - lat1!) * (p.lng - lng1!);
        return Math.abs(cross) < 1e-9;
      });
      expect(onRoute).toBe(true);
      expect(p.walkSeconds).toBeLessThan(15 * 60);
    }
  });

  it("returns a trip without pickup points when opened without a location", async () => {
    const [first] = await search("2026-10-20T13:30:00Z");
    expect((await tripDetail(first!.trip.id)).pickups).toEqual([]);
  });

  it("rejects only one of lat and lng, and an unknown trip", async () => {
    const [first] = await search("2026-10-20T13:30:00Z");
    const half = await tripDetail(first!.trip.id, { lat: 49.88 }).catch((e: unknown) => e);
    expect((half as ApiError).code).toBe("invalid_input");
    const missing = await tripDetail("99999999-9999-4999-8999-999999999999").catch((e: unknown) => e);
    expect((missing as ApiError).code).toBe("trip_not_found");
  });

  it("returns the driver's public profile", async () => {
    const [first] = await search("2026-10-20T13:30:00Z");
    const profile = await unwrap(accounts.GET("/users/{user_id}/profile", { params: { path: { user_id: first!.trip.driverId } } }));
    expect(profile.id).toBe(first!.trip.driverId);
    expect(profile.firstName).toBeTruthy();
    expect(profile.vehicle).not.toHaveProperty("plate");
  });
});
