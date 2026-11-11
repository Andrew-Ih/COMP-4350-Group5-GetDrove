import { http, HttpResponse } from "msw";

import type { components as Trips } from "@/shared/api/generated/trips";

import { maya } from "./data";

/**
 * Mock API for the rider's side of My trips (#131): GET /api/trips/requests/mine?when=,
 * matching the Trips contract. A made-up ride for each badge: pending, confirmed,
 * declined, a trip the driver cancelled, and a past ride.
 */

type RiderTrip = Trips["schemas"]["RiderTrip"];
type RequestStatus = Trips["schemas"]["RequestStatus"];

const CAMPUS = { label: "University Centre", lat: 49.8075, lng: -97.1366 };

function ride(
  tripId: string,
  daysAhead: number,
  time: string,
  status: RequestStatus,
  pickup: string,
  cents: number,
  tripStatus: Trips["schemas"]["TripStatus"] = "scheduled",
): RiderTrip {
  const departure = new Date();
  departure.setDate(departure.getDate() + daysAhead);
  const [hours, minutes] = time.split(":").map(Number);
  departure.setHours(hours!, minutes!, 0, 0);
  const createdAt = new Date(departure.getTime() - 2 * 24 * 3600_000).toISOString();
  return {
    trip: {
      id: tripId,
      driverId: `driver-${tripId}`,
      direction: "to_campus",
      origin: null, // the driver's end is private
      destination: CAMPUS,
      departureAt: departure.toISOString(),
      estimatedArrivalAt: new Date(departure.getTime() + 24 * 60_000).toISOString(),
      durationSeconds: 24 * 60,
      distanceMeters: 14_000,
      seatsTotal: 3,
      seatsAvailable: 1,
      status: tripStatus,
    },
    request: {
      id: `${tripId.slice(0, 8)}-1111-4111-8111-${tripId.slice(-12)}`,
      tripId,
      riderId: maya.id,
      status,
      pickup: { label: pickup, lat: 49.877, lng: -97.141, walkSeconds: 240 },
      cost: { amountCents: cents, currency: "CAD", explanation: `${(cents / 45).toFixed(1)} km at $0.45/km` },
      autoAccepted: false,
      createdAt,
      decidedAt: status === "pending" ? null : createdAt,
    },
  };
}

function rides(): { upcoming: RiderTrip[]; past: RiderTrip[] } {
  return {
    upcoming: [
      ride("22222222-2222-4222-8222-222222222222", 1, "07:52", "pending", "Osborne St & River Ave", 420),
      ride("33333333-3333-4333-8333-333333333333", 2, "07:40", "accepted", "Corydon Ave & Stafford St", 380),
      ride("44444444-4444-4444-8444-444444444444", 3, "07:50", "declined", "Osborne St & Wardlaw Ave", 440),
      ride("11111111-1111-4111-8111-111111111111", 5, "07:44", "cancelled", "River Ave & Nassau St", 460, "cancelled"),
    ],
    past: [ride("55555555-5555-4555-8555-555555555555", -2, "07:45", "accepted", "Osborne St & River Ave", 420, "completed")],
  };
}

export const myRidesHandlers = [
  http.get("*/api/trips/requests/mine", ({ request }) => {
    const when = new URL(request.url).searchParams.get("when") === "past" ? "past" : "upcoming";
    return HttpResponse.json(rides()[when]);
  }),
];
