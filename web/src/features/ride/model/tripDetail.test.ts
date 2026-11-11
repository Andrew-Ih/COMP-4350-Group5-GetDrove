import { describe, expect, it } from "vitest";

import { availability, type DriverProfile, driverLine, seatsAndDeparture, type TripDetail, tripDetailHref } from "./tripDetail";

// Local times, so the tests pass in any time zone.
const NOW = new Date("2026-10-15T20:00:00");
const at = (date: string, time: string) => new Date(`${date}T${time}`).toISOString();

const trip = (changes: Partial<TripDetail["trip"]> = {}): TripDetail["trip"] => ({
  id: "t1",
  driverId: "d1",
  direction: "to_campus",
  origin: null,
  destination: { label: "University Centre", lat: 49.8075, lng: -97.1366 },
  departureAt: at("2026-10-16", "07:48"),
  estimatedArrivalAt: at("2026-10-16", "08:12"),
  durationSeconds: 1440,
  distanceMeters: 14_000,
  seatsTotal: 3,
  seatsAvailable: 2,
  status: "scheduled",
  ...changes,
});

const priya: DriverProfile = {
  id: "d1",
  firstName: "Priya",
  rating: 4.9,
  ratingCount: 52,
  tripCount: 61,
  isDriver: true,
  vehicle: { make: "Honda", model: "Civic", colour: "Grey" },
};

describe("availability", () => {
  it("is open for a scheduled trip with a seat, before it leaves", () => {
    expect(availability(trip(), NOW)).toBe("open");
  });

  it("is full when no seats are left", () => {
    expect(availability(trip({ seatsAvailable: 0 }), NOW)).toBe("full");
  });

  it("is cancelled when the driver cancelled it, even with seats left", () => {
    expect(availability(trip({ status: "cancelled" }), NOW)).toBe("cancelled");
  });

  it("is departed once the trip is under way, finished or past its departure time", () => {
    expect(availability(trip({ status: "in_progress" }), NOW)).toBe("departed");
    expect(availability(trip({ status: "completed" }), NOW)).toBe("departed");
    expect(availability(trip({ departureAt: at("2026-10-15", "19:59") }), NOW)).toBe("departed");
  });
});

describe("seatsAndDeparture", () => {
  it("says how many seats are left and when the trip leaves", () => {
    expect(seatsAndDeparture(trip(), NOW)).toBe("2 of 3 seats left · departs 7:48 AM tomorrow");
  });

  it("names the day when it's further away", () => {
    expect(seatsAndDeparture(trip({ departureAt: at("2026-10-20", "07:48") }), NOW)).toBe(
      "2 of 3 seats left · departs 7:48 AM on Tue, Oct 20",
    );
  });
});

describe("driverLine", () => {
  it("shows the rating and the vehicle from the public profile", () => {
    expect(driverLine(priya, null)).toBe("★ 4.9 · Grey Honda Civic");
  });

  it("adds the plate once the trip sends the vehicle (the rider was accepted)", () => {
    expect(driverLine(priya, { make: "Honda", model: "Civic", colour: "Grey", plate: "ABC123" })).toBe(
      "★ 4.9 · Grey Honda Civic · ABC123",
    );
  });

  it("calls a driver without ratings a new driver", () => {
    expect(driverLine({ ...priya, rating: null, ratingCount: 0 }, null)).toBe("New driver · Grey Honda Civic");
  });

  it("is empty when the profile couldn't be loaded", () => {
    expect(driverLine(undefined, null)).toBe("");
  });
});

describe("tripDetailHref", () => {
  it("keeps the search, so the trip can find pickups and go back to the results", () => {
    const query = { lat: 49.8768, lng: -97.1438, direction: "to_campus" as const, time: "2026-10-16T13:30:00.000Z" };
    expect(tripDetailHref("t1", query)).toBe(
      "/ride/trip/t1?lat=49.87680&lng=-97.14380&direction=to_campus&time=2026-10-16T13%3A30%3A00.000Z",
    );
  });
});
