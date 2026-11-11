import { describe, expect, it } from "vitest";

import {
  canCancel,
  drivingRoute,
  formatWhen,
  isLateCancel,
  markCancelled,
  rideBadge,
  type RiderTrip,
  seatsFilled,
  type Trip,
  tripStatusLabel,
} from "./myTrips";

const NOW = new Date("2026-10-15T07:00:00");

const trip = (changes: Partial<Trip> = {}): Trip => ({
  id: "t1",
  driverId: "d1",
  direction: "to_campus",
  origin: { label: "Wolseley area", lat: 49.8794, lng: -97.1663 },
  destination: { label: "University Centre", lat: 49.8075, lng: -97.1366 },
  departureAt: new Date("2026-10-16T07:35:00").toISOString(),
  estimatedArrivalAt: new Date("2026-10-16T07:57:00").toISOString(),
  durationSeconds: 1320,
  distanceMeters: 11_800,
  seatsTotal: 3,
  seatsAvailable: 1,
  status: "scheduled",
  ...changes,
});

const ride = (status: RiderTrip["request"]["status"], tripChanges: Partial<Trip> = {}): RiderTrip => ({
  trip: trip({ origin: null, ...tripChanges }),
  request: {
    id: "r1",
    tripId: "t1",
    riderId: "me",
    status,
    pickup: { label: "Osborne St & River Ave", lat: 49.8768, lng: -97.1438, walkSeconds: 240 },
    cost: { amountCents: 420, currency: "CAD", explanation: "9.3 km at $0.45/km" },
    autoAccepted: false,
    createdAt: "2026-10-14T12:00:00Z",
    decidedAt: null,
  },
});

describe("formatWhen", () => {
  it("shows the day and time", () => {
    expect(formatWhen(new Date("2026-10-16T07:35:00").toISOString())).toBe("Fri, Oct 16 · 7:35 AM");
    expect(formatWhen(new Date("2026-10-16T17:05:00").toISOString())).toBe("Fri, Oct 16 · 5:05 PM");
  });
});

describe("drivingRoute", () => {
  it("names the driver's own end and campus, in the direction of travel", () => {
    expect(drivingRoute(trip())).toBe("Wolseley area → U of M Fort Garry");
    const home = trip({ direction: "from_campus", origin: { label: "University Centre", lat: 0, lng: 0 }, destination: { label: "Wolseley area", lat: 0, lng: 0 } });
    expect(drivingRoute(home)).toBe("U of M Fort Garry → Wolseley area");
  });
});

describe("seatsFilled and tripStatusLabel", () => {
  it("counts the seats taken", () => {
    expect(seatsFilled(trip())).toBe("2 of 3 seats filled");
  });

  it("labels every state but scheduled", () => {
    expect(tripStatusLabel(trip())).toBeUndefined();
    expect(tripStatusLabel(trip({ status: "cancelled" }))).toBe("Cancelled");
    expect(tripStatusLabel(trip({ status: "completed" }))).toBe("Completed");
    expect(tripStatusLabel(trip({ status: "in_progress" }))).toBe("Under way");
  });
});

describe("cancelling", () => {
  it("is allowed for a scheduled trip that hasn't left", () => {
    expect(canCancel(trip(), NOW)).toBe(true);
    expect(canCancel(trip({ status: "cancelled" }), NOW)).toBe(false);
    expect(canCancel(trip({ status: "in_progress" }), NOW)).toBe(false);
    expect(canCancel(trip({ departureAt: new Date("2026-10-15T06:59:00").toISOString() }), NOW)).toBe(false);
  });

  it("is late less than an hour before departure", () => {
    expect(isLateCancel(trip({ departureAt: new Date("2026-10-15T07:59:00").toISOString() }), NOW)).toBe(true);
    expect(isLateCancel(trip({ departureAt: new Date("2026-10-15T08:00:00").toISOString() }), NOW)).toBe(false);
  });

  it("marks the cancelled trips in a list", () => {
    const other = trip({ id: "t2" });
    const list = markCancelled([trip(), other], [trip({ status: "cancelled" })]);
    expect(list.map((t) => t.status)).toEqual(["cancelled", "scheduled"]);
  });
});

describe("rideBadge", () => {
  it("shows the request's status", () => {
    expect(rideBadge(ride("pending"))).toEqual({ label: "Pending", tone: "pending" });
    expect(rideBadge(ride("accepted"))).toEqual({ label: "Confirmed", tone: "confirmed" });
    expect(rideBadge(ride("declined")).label).toBe("Declined");
    expect(rideBadge(ride("cancelled")).label).toBe("Cancelled");
    expect(rideBadge(ride("expired")).label).toBe("Expired");
    expect(rideBadge(ride("payment_failed")).label).toBe("Payment failed");
  });

  it("says the trip was cancelled when the driver cancelled it", () => {
    expect(rideBadge(ride("cancelled", { status: "cancelled" }))).toEqual({ label: "Trip cancelled", tone: "ended" });
  });

  it("calls a confirmed ride on a finished trip completed", () => {
    expect(rideBadge(ride("accepted", { status: "completed" }))).toEqual({ label: "Completed", tone: "done" });
  });
});
