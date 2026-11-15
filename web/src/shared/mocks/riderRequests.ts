import { http, HttpResponse } from "msw";

import type { components as Trips } from "@/shared/api/generated/trips";

import { driverProfile, isSearchTrip, maya } from "./data";

/**
 * Mock API for a rider asking for a seat (#141), matching the Trips contract. Each of the
 * four search trips behaves differently, so every state can be tried:
 *   - Amira's trip (1 seat left)      → 409 trip_full ("that seat was just taken"), then full
 *   - Priya's trip                     → pending, then accepted after two checks (~20 s)
 *   - Daniel's trip                    → pending, then declined after two checks
 *   - Jordan's trip                    → 409 card_required
 * All four trips are around the same time, so with a request already pending or accepted,
 * asking on another trip gives 409 overlapping_request. Cancelling works from either state.
 */

type SeatRequest = Trips["schemas"]["SeatRequest"];
type TripDetail = Trips["schemas"]["TripDetail"];
type PickupOption = Trips["schemas"]["PickupOption"];

const AMIRA = "11111111-1111-4111-8111-111111111111";
const PRIYA = "22222222-2222-4222-8222-222222222222";
const DANIEL = "33333333-3333-4333-8333-333333333333";
const JORDAN = "44444444-4444-4444-8444-444444444444";

/** What happens to a pending request after it's been checked twice. */
const DECISION: Record<string, "accepted" | "declined" | undefined> = { [PRIYA]: "accepted", [DANIEL]: "declined" };
const CHECKS_BEFORE_DECISION = 2;

// The rider's requests, the times each was checked, and the pickup points last offered per trip.
const requests = new Map<string, SeatRequest>();
const checks = new Map<string, number>();
const offered = new Map<string, PickupOption[]>();
// Trips whose last seat went to someone else while the rider was asking: shown as full.
const taken = new Set<string>();

/** Forgets the rider's requests (for tests). */
export function resetRiderRequests() {
  requests.clear();
  checks.clear();
  offered.clear();
  taken.clear();
}

const isActive = (r: SeatRequest) => r.status === "pending" || r.status === "accepted";

function activeOn(tripId: string): SeatRequest | undefined {
  return [...requests.values()].find((r) => r.tripId === tripId && isActive(r));
}

/**
 * The trip detail with the rider's own pending or accepted request. Once accepted, it
 * takes a seat and the car's plate comes with it. Also remembers the pickup points
 * offered, so a request can be checked against them.
 */
export function withMyRequest(detail: TripDetail): TripDetail {
  if (detail.pickups.length > 0) offered.set(detail.trip.id, detail.pickups);
  if (taken.has(detail.trip.id)) return { ...detail, trip: { ...detail.trip, seatsAvailable: 0 } };
  const mine = activeOn(detail.trip.id);
  if (!mine) return detail;
  if (mine.status !== "accepted") return { ...detail, myRequest: mine };
  const car = driverProfile(detail.trip.driverId)?.vehicle;
  return {
    ...detail,
    trip: { ...detail.trip, seatsAvailable: Math.max(0, detail.trip.seatsAvailable - 1) },
    vehicle: car ? { ...car, plate: "GDR123" } : null,
    myRequest: mine,
  };
}

function problem(status: number, code: string, detail: string, instance: string) {
  return HttpResponse.json(
    { type: "about:blank", title: detail, status, detail, instance, code, requestId: "mock" },
    { status, headers: { "Content-Type": "application/problem+json" } },
  );
}

export const riderRequestHandlers = [
  http.post("*/api/trips/:tripId/requests", async ({ params, request }) => {
    const tripId = String(params.tripId);
    const instance = `/api/trips/${tripId}/requests`;
    const body = (await request.json()) as Trips["schemas"]["SeatRequestBody"];
    if ((body.exclude?.length ?? 0) > 20) return problem(422, "invalid_input", "Invalid input", instance);
    if (!isSearchTrip(tripId)) return problem(404, "trip_not_found", "No trip with this ID", instance);
    if (activeOn(tripId)) return problem(409, "already_requested", "You've already asked for a seat on this trip", instance);
    if ([...requests.values()].some(isActive)) {
      return problem(409, "overlapping_request", "You have another request around this time", instance);
    }
    if (tripId === AMIRA) {
      taken.add(tripId);
      return problem(409, "trip_full", "No seats left on this trip", instance);
    }
    if (tripId === JORDAN) return problem(409, "card_required", "Add a card before requesting a seat", instance);
    // The points last offered on the trip detail, which were found with the same `exclude`.
    const pickup = offered.get(tripId)?.find((p) => p.id === body.pickupId);
    if (!pickup) return problem(422, "pickup_not_available", "This pickup point isn't available from where you are", instance);

    const created: SeatRequest = {
      id: crypto.randomUUID(),
      tripId,
      riderId: maya.id,
      status: "pending",
      pickup: { label: pickup.label, lat: pickup.lat, lng: pickup.lng, walkSeconds: pickup.walkSeconds },
      cost: pickup.cost ?? { amountCents: 0, currency: "CAD", explanation: "Not priced" },
      autoAccepted: false,
      createdAt: new Date().toISOString(),
      decidedAt: null,
    };
    requests.set(created.id, created);
    return HttpResponse.json(created, { status: 201 });
  }),

  // A pending request is decided once it's been checked a couple of times.
  http.get("*/api/trips/requests/:requestId", ({ params }) => {
    const requestId = String(params.requestId);
    if (requestId === "mine") return undefined; // the rider's trips list, not a request
    const found = requests.get(requestId);
    if (!found) return problem(404, "request_not_found", "No request with this ID", `/api/trips/requests/${requestId}`);
    if (found.status === "pending") {
      const count = (checks.get(requestId) ?? 0) + 1;
      checks.set(requestId, count);
      const decision = DECISION[found.tripId];
      if (decision && count >= CHECKS_BEFORE_DECISION) {
        found.status = decision;
        found.decidedAt = new Date().toISOString();
      }
    }
    return HttpResponse.json(found);
  }),

  http.post("*/api/trips/requests/:requestId/cancel", ({ params }) => {
    const requestId = String(params.requestId);
    const instance = `/api/trips/requests/${requestId}/cancel`;
    const found = requests.get(requestId);
    if (!found) return problem(404, "request_not_found", "No request with this ID", instance);
    if (!isActive(found)) return problem(409, "request_not_cancellable", "This request can't be cancelled", instance);
    found.status = "cancelled";
    found.decidedAt = new Date().toISOString();
    return HttpResponse.json(found);
  }),
];
