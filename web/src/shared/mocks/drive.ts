import { delay, http, HttpResponse } from "msw";

import type { components as Routing } from "@/shared/api/generated/routing";
import type { components as Trips } from "@/shared/api/generated/trips";

/**
 * Mock API for posting a trip (#96), matching POST /api/trips/ and the route of a posted
 * trip. Special inputs to try the error states:
 *   - a departure in the past              → 422 departure_in_past
 *   - a departure time ending in :55       → 503 routing_unavailable (nothing saved)
 * Posted trips are listed by GET /api/trips/mine?role=driver, so the "you already have a
 * trip then" warning can be tried too.
 */

const CAMPUS = { label: "University Centre", lat: 49.8075, lng: -97.1366 };
const ROAD_FACTOR = 1.35; // roads are longer than a straight line
const METERS_PER_SECOND = 10; // about 36 km/h, city driving

// Trips posted in this session, and their routes for GET /routing/trips/{id}/geometry.
const postedTrips: Trips["schemas"]["Trip"][] = [];
const posted = new Map<string, Routing["schemas"]["RouteFeature"]>();

/** Forgets the trips posted so far (for tests). */
export function resetPostedTrips() {
  postedTrips.length = 0;
  posted.clear();
}

function straightLineMeters(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h));
}

function problem(status: number, code: string, detail: string, extra: object = {}) {
  return HttpResponse.json(
    { type: "about:blank", title: detail, status, detail, instance: "/api/trips/", code, requestId: "mock", ...extra },
    { status, headers: { "Content-Type": "application/problem+json" } },
  );
}

export const driveHandlers = [
  http.post("*/api/trips/", async ({ request }) => {
    const body = (await request.json()) as Trips["schemas"]["PostTripRequest"];
    await delay(); // realistic in the browser, none in tests
    const departure = new Date(body.departureAt);
    if (departure.getTime() <= Date.now()) {
      return problem(422, "departure_in_past", "The departure must be in the future", {
        errors: [{ field: "departureAt", message: "Must be in the future" }],
      });
    }
    if (departure.getUTCMinutes() === 55) {
      return problem(503, "routing_unavailable", "The route couldn't be computed right now");
    }

    const meters = Math.round(straightLineMeters(body.place, CAMPUS) * ROAD_FACTOR);
    const seconds = Math.round(meters / METERS_PER_SECOND);
    const trip: Trips["schemas"]["Trip"] = {
      id: crypto.randomUUID(),
      driverId: "7a0c8d8e-3c38-4a5e-9a59-1d1f0b7f6b11",
      direction: body.direction,
      // The driver gets their own end back; riders would get null.
      origin: body.direction === "to_campus" ? body.place : CAMPUS,
      destination: body.direction === "to_campus" ? CAMPUS : body.place,
      departureAt: departure.toISOString(),
      estimatedArrivalAt: new Date(departure.getTime() + seconds * 1000).toISOString(),
      durationSeconds: seconds,
      distanceMeters: meters,
      seatsTotal: body.seatsTotal,
      seatsAvailable: body.seatsTotal,
      status: "scheduled",
    };

    // A rough road-like line: east or west first, then south to campus. Real routes come
    // from OSRM and follow the roads.
    const corner: [number, number] = [CAMPUS.lng + 0.004, body.place.lat];
    const toCampus: [number, number][] = [[body.place.lng, body.place.lat], corner, [CAMPUS.lng, CAMPUS.lat]];
    posted.set(trip.id, {
      type: "Feature",
      geometry: { type: "LineString", coordinates: body.direction === "to_campus" ? toCampus : [...toCampus].reverse() },
      properties: { tripId: trip.id, distanceMeters: meters, durationSeconds: seconds },
    });
    postedTrips.push(trip);
    return HttpResponse.json(trip, { status: 201 });
  }),

  // The driver's upcoming trips: the ones posted here, soonest first. role=rider falls
  // through to the next handler.
  http.get("*/api/trips/mine", ({ request }) => {
    const role = new URL(request.url).searchParams.get("role") ?? "driver";
    if (role !== "driver") return undefined;
    const upcoming = postedTrips
      .filter((trip) => Date.parse(trip.estimatedArrivalAt) > Date.now())
      .sort((a, b) => Date.parse(a.departureAt) - Date.parse(b.departureAt));
    return HttpResponse.json(upcoming);
  }),

  // Routes of trips posted here. Any other trip falls through to the next handler.
  http.get("*/api/routing/trips/:tripId/geometry", ({ params }) => {
    const route = posted.get(String(params.tripId));
    return route ? HttpResponse.json(route) : undefined;
  }),
];
