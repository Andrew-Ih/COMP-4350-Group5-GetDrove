import { describe, expect, it } from "vitest";

import type { Trip } from "./postTrip";
import {
  applyDecision,
  canDecide,
  type DriverRequest,
  formatDetour,
  pickupOrderLabel,
  riderLine,
  routeLine,
  seatsFilled,
  seatsLeftLine,
  splitRequests,
} from "./requests";

const NOW = new Date("2026-10-15T20:00:00");

const trip = (changes: Partial<Trip> = {}): Trip => ({
  id: "t1",
  driverId: "d1",
  direction: "to_campus",
  origin: { label: "Wolseley Ave & Arlington St", lat: 49.8794, lng: -97.1663 },
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

function request(id: string, status: "pending" | "accepted", pickupOrder: number | null = null): DriverRequest {
  return {
    id,
    status,
    rider: { id: `r-${id}`, firstName: id, rating: 4.8, ratingCount: 10, noShowCount: 0 },
    pickup: { label: "Osborne St & River Ave", lat: 49.8768, lng: -97.1438 },
    pickupOrder,
    detourSeconds: 180,
    cost: { amountCents: 420, currency: "CAD", explanation: "9.3 km at $0.45/km" },
    autoAccepted: false,
    createdAt: "2026-10-15T19:00:00Z",
    decidedAt: null,
  };
}

describe("formatDetour", () => {
  it("rounds up to whole minutes, so a short detour isn't shown as none", () => {
    expect(formatDetour(180)).toBe("+3 min");
    expect(formatDetour(61)).toBe("+2 min");
  });

  it("says when a pickup is right on the route", () => {
    expect(formatDetour(0)).toBe("No detour");
    expect(formatDetour(20)).toBe("No detour");
  });

  it("gives no number when the detour couldn't be worked out", () => {
    expect(formatDetour(null)).toBeUndefined();
  });
});

describe("riderLine", () => {
  it("shows the rating and no-shows", () => {
    expect(riderLine({ id: "r", firstName: "Ethan", rating: 4.6, ratingCount: 9, noShowCount: 1 })).toBe("★ 4.6 · 1 no-show");
    expect(riderLine({ id: "r", firstName: "Amara", rating: 5, ratingCount: 3, noShowCount: 0 })).toBe("★ 5.0 · 0 no-shows");
  });

  it("calls a rider without ratings a new rider", () => {
    expect(riderLine({ id: "r", firstName: "Sofia", rating: null, ratingCount: 0, noShowCount: 0 })).toBe("New rider · 0 no-shows");
  });
});

describe("splitRequests", () => {
  it("keeps pending requests in order and puts accepted riders in pickup order", () => {
    const { pending, accepted } = splitRequests([request("b", "accepted", 2), request("x", "pending"), request("a", "accepted", 1), request("y", "pending")]);
    expect(pending.map((r) => r.id)).toEqual(["x", "y"]);
    expect(accepted.map((r) => r.id)).toEqual(["a", "b"]);
  });
});

describe("the trip card", () => {
  it("names both ends and counts the seats", () => {
    expect(routeLine(trip())).toBe("Wolseley Ave & Arlington St → University Centre");
    expect(seatsFilled(trip())).toBe("2 of 3 seats filled");
    expect(seatsLeftLine(trip())).toBe("1 seat left");
    expect(seatsLeftLine(trip({ seatsAvailable: 2 }))).toBe("2 seats left");
    expect(seatsLeftLine(trip({ seatsAvailable: 0 }))).toBe("No seats left");
  });
});

describe("pickupOrderLabel", () => {
  it("says where the rider is in the pickup order", () => {
    expect(pickupOrderLabel(1)).toBe("1st pickup");
    expect(pickupOrderLabel(2)).toBe("2nd pickup");
    expect(pickupOrderLabel(3)).toBe("3rd pickup");
    expect(pickupOrderLabel(4)).toBe("4th pickup");
    expect(pickupOrderLabel(null)).toBeUndefined();
  });
});

describe("canDecide", () => {
  it("allows decisions on a scheduled trip that hasn't left", () => {
    expect(canDecide(trip(), NOW)).toBe(true);
  });

  it("doesn't once the trip is cancelled, under way or past its departure", () => {
    expect(canDecide(trip({ status: "cancelled" }), NOW)).toBe(false);
    expect(canDecide(trip({ status: "in_progress" }), NOW)).toBe(false);
    expect(canDecide(trip({ departureAt: new Date("2026-10-15T19:00:00").toISOString() }), NOW)).toBe(false);
  });
});

describe("applyDecision", () => {
  const requests = [request("a", "accepted", 1), request("x", "pending"), request("y", "pending")];

  it("accepting moves the request to the riders and takes a seat", () => {
    const next = applyDecision(trip(), requests, "x", "accepted");
    expect(next.trip.seatsAvailable).toBe(0);
    expect(next.requests.find((r) => r.id === "x")).toMatchObject({ status: "accepted", pickupOrder: 2 });
  });

  it("declining a pending request removes it and leaves the seats alone", () => {
    const next = applyDecision(trip(), requests, "y", "declined");
    expect(next.trip.seatsAvailable).toBe(1);
    expect(next.requests.map((r) => r.id)).toEqual(["a", "x"]);
  });

  it("declining an accepted rider frees their seat", () => {
    const next = applyDecision(trip(), requests, "a", "declined");
    expect(next.trip.seatsAvailable).toBe(2);
  });

  it("changes nothing for a request that isn't there", () => {
    expect(applyDecision(trip(), requests, "gone", "accepted")).toEqual({ trip: trip(), requests });
  });
});
