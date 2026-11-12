import { delay, http, HttpResponse } from "msw";

import type { components as Routing } from "@/shared/api/generated/routing";
import type { components as Trips } from "@/shared/api/generated/trips";

/**
 * Mock API for posting a trip (#96), matching POST /api/trips/ and the route of a posted
 * trip. Special inputs to try the error states:
 *   - a departure in the past              → 422 departure_in_past
 *   - a departure time ending in :55       → 503 routing_unavailable (nothing saved)
 * Posted trips are listed by GET /api/trips/mine, so the "you already have a trip then"
 * warning can be tried too.
 *
 * My trips (#131, #133): the list also has a few made-up trips, so every case shows: a
 * recurring series (cancel one day or all of it), a trip leaving in 45 minutes (the late
 * cancellation warning), a cancelled one and a past one. POST /api/trips/{id}/cancel and
 * /api/trips/series/{id}/cancel cancel them.
 */

const CAMPUS = { label: "University Centre", lat: 49.8075, lng: -97.1366 };
const ROAD_FACTOR = 1.35; // roads are longer than a straight line
const METERS_PER_SECOND = 10; // about 36 km/h, city driving

type Trip = Trips["schemas"]["Trip"];

// Trips posted in this session, and their routes for GET /routing/trips/{id}/geometry.
const postedTrips: Trip[] = [];
const posted = new Map<string, Routing["schemas"]["RouteFeature"]>();

/** A made-up trip of the driver's, `daysAhead` days from today at `time` (negative: in the past). */
function myTrip(id: string, daysAhead: number, time: string, changes: Partial<Trip> = {}): Trip {
  const departure = new Date();
  departure.setDate(departure.getDate() + daysAhead);
  const [hours, minutes] = time.split(":").map(Number);
  departure.setHours(hours!, minutes!, 0, 0);
  const seconds = 22 * 60;
  return {
    id,
    driverId: "7a0c8d8e-3c38-4a5e-9a59-1d1f0b7f6b11",
    direction: "to_campus",
    origin: { label: "Wolseley area", lat: 49.8794, lng: -97.1663 },
    destination: CAMPUS,
    departureAt: departure.toISOString(),
    estimatedArrivalAt: new Date(departure.getTime() + seconds * 1000).toISOString(),
    durationSeconds: seconds,
    distanceMeters: 11_800,
    seatsTotal: 3,
    seatsAvailable: 2,
    status: "scheduled",
    seriesId: null,
    ...changes,
  };
}

const SERIES_ID = "77777777-7777-4777-8777-777777777777";

/** The made-up trips My trips starts with. */
function exampleTrips(): Trip[] {
  const soon = Date.now() + 45 * 60_000;
  return [
    myTrip("77777777-0000-4000-8000-000000000001", 2, "08:00", { seriesId: SERIES_ID }),
    myTrip("77777777-0000-4000-8000-000000000002", 3, "08:00", { seriesId: SERIES_ID, seatsAvailable: 3 }),
    myTrip("77777777-0000-4000-8000-000000000003", 0, "00:00", {
      departureAt: new Date(soon).toISOString(),
      estimatedArrivalAt: new Date(soon + 22 * 60_000).toISOString(),
      direction: "from_campus",
      origin: CAMPUS,
      destination: { label: "Osborne Village area", lat: 49.8768, lng: -97.1438 },
      seatsTotal: 2,
      seatsAvailable: 0,
    }),
    myTrip("77777777-0000-4000-8000-000000000004", 4, "17:00", { direction: "from_campus", origin: CAMPUS, destination: { label: "Wolseley area", lat: 49.8794, lng: -97.1663 }, status: "cancelled" }),
    myTrip("77777777-0000-4000-8000-000000000005", -3, "07:45", { status: "completed", seatsAvailable: 1 }),
  ];
}

let examples = exampleTrips();

/** Forgets the trips posted so far, and puts the made-up ones back (for tests). */
export function resetPostedTrips() {
  postedTrips.length = 0;
  posted.clear();
  examples = exampleTrips();
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

  // The driver's trips, cancelled ones included: upcoming (not arrived yet, soonest first)
  // or past (most recent first).
  http.get("*/api/trips/mine", ({ request }) => {
    const when = new URL(request.url).searchParams.get("when") === "past" ? "past" : "upcoming";
    const all = [...postedTrips, ...examples];
    const upcoming = (trip: Trip) => Date.parse(trip.estimatedArrivalAt) > Date.now() && trip.status !== "completed";
    const list =
      when === "upcoming"
        ? all.filter(upcoming).sort((a, b) => Date.parse(a.departureAt) - Date.parse(b.departureAt))
        : all.filter((t) => !upcoming(t)).sort((a, b) => Date.parse(b.departureAt) - Date.parse(a.departureAt));
    return HttpResponse.json(list);
  }),

  // Cancelling one trip: only a scheduled one that hasn't left.
  http.post("*/api/trips/:tripId/cancel", ({ params }) => {
    const tripId = String(params.tripId);
    const trip = [...postedTrips, ...examples].find((t) => t.id === tripId);
    if (!trip) return problem(404, "trip_not_found", "No trip with this ID");
    if (trip.status !== "scheduled" || Date.parse(trip.departureAt) <= Date.now()) {
      return problem(409, "trip_not_cancellable", "The trip has already started, finished or been cancelled");
    }
    trip.status = "cancelled";
    return HttpResponse.json(trip);
  }),

  // Cancelling a series: every trip in it that hasn't started.
  http.post("*/api/trips/series/:seriesId/cancel", ({ params }) => {
    const seriesId = String(params.seriesId);
    const inSeries = [...postedTrips, ...examples].filter((t) => t.seriesId === seriesId);
    if (inSeries.length === 0) return problem(404, "series_not_found", "No series with this ID");
    const cancelled = inSeries.filter((t) => t.status === "scheduled" && Date.parse(t.departureAt) > Date.now());
    for (const trip of cancelled) trip.status = "cancelled";
    return HttpResponse.json(cancelled);
  }),

  // Routes of trips posted here. Any other trip falls through to the next handler.
  http.get("*/api/routing/trips/:tripId/geometry", ({ params }) => {
    const route = posted.get(String(params.tripId));
    return route ? HttpResponse.json(route) : undefined;
  }),
];
