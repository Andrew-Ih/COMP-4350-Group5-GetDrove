import { http, HttpResponse } from "msw";

import type { components as Routing } from "@/shared/api/generated/routing";
import type { components as Trips } from "@/shared/api/generated/trips";

import { isSearchTrip, maya } from "./data";
import { findPosted } from "./drive";

/**
 * Mock API for the driver's side of seat requests (#142), matching the Trips contract:
 * a trip's requests, accepting and declining them, and the trip itself for its driver.
 *
 * There's always one demo trip to try it on, from Wolseley tomorrow at 7:35 AM, with two
 * riders accepted, one seat left and three requests:
 *   /drive/trips/66666666-6666-4666-8666-666666666666
 * Sofia's detour can't be worked out the first time (null, the error state); asking again
 * gives a number. Accepting one request fills the trip.
 *
 * A trip posted in this session gets two requests along its route, so "See requests"
 * after posting works too. Other drivers' trips (the ones searches return) answer 403
 * `not_trip_driver`, and unknown trips 404 `trip_not_found`.
 */

type Trip = Trips["schemas"]["Trip"];
type DriverRequest = Trips["schemas"]["DriverRequestView"];
type RouteFeature = Routing["schemas"]["RouteFeature"];

export const DEMO_TRIP_ID = "66666666-6666-4666-8666-666666666666";

const CAMPUS = { label: "University Centre", lat: 49.8075, lng: -97.1366 };

function tomorrowAt(hours: number, minutes: number): Date {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(hours, minutes, 0, 0);
  return date;
}

function rider(id: string, firstName: string, rating: number | null, noShowCount: number) {
  return { id, firstName, rating, ratingCount: rating === null ? 0 : 12, noShowCount };
}

function request(
  id: string,
  who: DriverRequest["rider"],
  pickup: DriverRequest["pickup"],
  status: "pending" | "accepted",
  detourSeconds: number | null,
  pickupOrder: number | null = null,
): DriverRequest {
  const createdAt = new Date(Date.now() - 3600_000).toISOString();
  return {
    id,
    status,
    rider: who,
    pickup,
    pickupOrder,
    detourSeconds,
    cost: { amountCents: 420, currency: "CAD", explanation: "9.3 km at $0.45/km" },
    autoAccepted: false,
    createdAt,
    decidedAt: status === "accepted" ? createdAt : null,
  };
}

type DriverTrip = { trip: Trip; route: RouteFeature; requests: DriverRequest[]; retriedDetours: Set<string> };

// The demo trip and the requests on trips posted in this session, by trip ID.
const trips = new Map<string, DriverTrip>();

function demoTrip(): DriverTrip {
  const departure = tomorrowAt(7, 35);
  const seconds = 22 * 60;
  const start = { label: "Wolseley Ave & Arlington St", lat: 49.8794, lng: -97.1663 };
  // A rough line along Osborne St and Pembina Hwy. Real routes come from OSRM.
  const coordinates: [number, number][] = [
    [start.lng, start.lat],
    [-97.1438, 49.8768],
    [-97.1442, 49.868],
    [-97.1497, 49.8573],
    [-97.15, 49.83],
    [CAMPUS.lng, CAMPUS.lat],
  ];
  return {
    trip: {
      id: DEMO_TRIP_ID,
      driverId: maya.id,
      direction: "to_campus",
      origin: start,
      destination: CAMPUS,
      departureAt: departure.toISOString(),
      estimatedArrivalAt: new Date(departure.getTime() + seconds * 1000).toISOString(),
      durationSeconds: seconds,
      distanceMeters: 11_800,
      seatsTotal: 3,
      seatsAvailable: 1,
      status: "scheduled",
    },
    route: {
      type: "Feature",
      geometry: { type: "LineString", coordinates },
      properties: { tripId: DEMO_TRIP_ID, distanceMeters: 11_800, durationSeconds: seconds },
    },
    requests: [
      request("a1a1a1a1-0000-4000-8000-000000000001", rider("r-amara", "Amara", 4.9, 0), { label: "Osborne St & River Ave", lat: 49.8768, lng: -97.1438 }, "pending", 180),
      request("a1a1a1a1-0000-4000-8000-000000000002", rider("r-ethan", "Ethan", 4.6, 1), { label: "Corydon Ave & Stafford St", lat: 49.8698, lng: -97.1543 }, "pending", 300),
      request("a1a1a1a1-0000-4000-8000-000000000003", rider("r-sofia", "Sofia", null, 0), { label: "Pembina Hwy & Jubilee Ave", lat: 49.8573, lng: -97.1497 }, "pending", null),
      request("a1a1a1a1-0000-4000-8000-000000000004", rider("r-liam", "Liam", 4.8, 0), { label: "Osborne St & Grant Ave", lat: 49.868, lng: -97.1442 }, "accepted", 120, 1),
      request("a1a1a1a1-0000-4000-8000-000000000005", rider("r-noor", "Noor", 5.0, 0), { label: "Pembina Hwy & Bishop Grandin Blvd", lat: 49.83, lng: -97.15 }, "accepted", 150, 2),
    ],
    retriedDetours: new Set(),
  };
}

/** Puts the demo trip back as it started (for tests, and at startup). */
export function resetDriverRequests() {
  trips.clear();
  trips.set(DEMO_TRIP_ID, demoTrip());
}
resetDriverRequests();

/** The demo trip, or a trip posted in this session with two requests along its route. */
function driverTrip(tripId: string): DriverTrip | undefined {
  const known = trips.get(tripId);
  if (known) return known;
  const found = findPosted(tripId);
  if (!found) return undefined;
  const [first, second] = found.route.geometry.coordinates;
  const along = (t: number) => ({ lng: first![0]! + (second![0]! - first![0]!) * t, lat: first![1]! + (second![1]! - first![1]!) * t });
  const created: DriverTrip = {
    trip: found.trip,
    route: found.route,
    requests: [
      request(`${tripId.slice(0, 8)}-0000-4000-8000-000000000001`, rider("r-amara", "Amara", 4.9, 0), { label: "On your route, near the start", ...along(0.3) }, "pending", 120),
      request(`${tripId.slice(0, 8)}-0000-4000-8000-000000000002`, rider("r-ethan", "Ethan", 4.6, 1), { label: "On your route, further along", ...along(0.7) }, "pending", 240),
    ],
    retriedDetours: new Set(),
  };
  trips.set(tripId, created);
  return created;
}

function problem(status: number, code: string, detail: string, instance: string) {
  return HttpResponse.json(
    { type: "about:blank", title: detail, status, detail, instance, code, requestId: "mock" },
    { status, headers: { "Content-Type": "application/problem+json" } },
  );
}

function asSeatRequest(tripId: string, r: DriverRequest): Trips["schemas"]["SeatRequest"] {
  return {
    id: r.id,
    tripId,
    riderId: r.rider.id,
    status: r.status,
    pickup: { ...r.pickup, walkSeconds: 240 },
    cost: r.cost,
    autoAccepted: r.autoAccepted,
    createdAt: r.createdAt,
    decidedAt: r.decidedAt,
  };
}

function findRequest(requestId: string) {
  for (const entry of trips.values()) {
    const found = entry.requests.find((r) => r.id === requestId);
    if (found) return { entry, found };
  }
  return undefined;
}

export const requestHandlers = [
  // Pending first, then accepted in pickup order. Declined and cancelled ones are left out.
  http.get("*/api/trips/:tripId/requests", ({ params }) => {
    const tripId = String(params.tripId);
    const instance = `/api/trips/${tripId}/requests`;
    const entry = driverTrip(tripId);
    if (!entry && isSearchTrip(tripId)) return problem(403, "not_trip_driver", "Only the trip's driver can see its requests", instance);
    if (!entry) return problem(404, "trip_not_found", "No trip with this ID", instance);
    const list = entry.requests.map((r) => {
      // A detour that couldn't be worked out works the next time it's asked for.
      if (r.detourSeconds === null && entry.retriedDetours.has(r.id)) return { ...r, detourSeconds: 240 };
      if (r.detourSeconds === null) entry.retriedDetours.add(r.id);
      return r;
    });
    const pending = list.filter((r) => r.status === "pending");
    const accepted = list.filter((r) => r.status === "accepted").sort((a, b) => (a.pickupOrder ?? 0) - (b.pickupOrder ?? 0));
    return HttpResponse.json([...pending, ...accepted]);
  }),

  http.post("*/api/trips/requests/:requestId/accept", ({ params }) => {
    const requestId = String(params.requestId);
    const instance = `/api/trips/requests/${requestId}/accept`;
    const match = findRequest(requestId);
    if (!match) return problem(404, "request_not_found", "No request with this ID", instance);
    const { entry, found } = match;
    if (found.status !== "pending") return problem(409, "request_not_pending", "This request isn't pending", instance);
    if (entry.trip.seatsAvailable === 0) return problem(409, "seat_taken", "No seat left on this trip", instance);
    found.status = "accepted";
    found.decidedAt = new Date().toISOString();
    found.pickupOrder = entry.requests.filter((r) => r.status === "accepted").length;
    entry.trip.seatsAvailable -= 1;
    return HttpResponse.json(asSeatRequest(entry.trip.id, found));
  }),

  http.post("*/api/trips/requests/:requestId/decline", ({ params }) => {
    const requestId = String(params.requestId);
    const instance = `/api/trips/requests/${requestId}/decline`;
    const match = findRequest(requestId);
    if (!match) return problem(404, "request_not_found", "No request with this ID", instance);
    const { entry, found } = match;
    if (found.status !== "pending" && found.status !== "accepted") {
      return problem(409, "request_not_decidable", "This request can't be declined", instance);
    }
    if (found.status === "accepted") entry.trip.seatsAvailable += 1;
    found.status = "declined";
    found.decidedAt = new Date().toISOString();
    found.pickupOrder = null;
    const declined = asSeatRequest(entry.trip.id, found);
    entry.requests = entry.requests.filter((r) => r.id !== requestId);
    return HttpResponse.json(declined);
  }),

  // The trip itself for its driver, with their own end. Any other trip falls through.
  http.get("*/api/trips/:tripId", ({ params }) => {
    const entry = driverTrip(String(params.tripId));
    if (!entry) return undefined;
    const detail: Trips["schemas"]["TripDetail"] = { trip: entry.trip, vehicle: null, pickups: [], myRequest: null };
    return HttpResponse.json(detail);
  }),

  // The demo trip's route. Posted trips' routes are in drive.ts.
  http.get("*/api/routing/trips/:tripId/geometry", ({ params }) => {
    const entry = trips.get(String(params.tripId));
    return entry && entry.trip.id === DEMO_TRIP_ID ? HttpResponse.json(entry.route) : undefined;
  }),
];
