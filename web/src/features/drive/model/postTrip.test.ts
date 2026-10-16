import { describe, expect, it } from "vitest";

import { toSearchTime } from "@/features/ride";

import {
  buildPostTrip,
  defaultDeparture,
  findOverlap,
  formatClock,
  formatDistance,
  formatDuration,
  overlapMessage,
  placeLabel,
  type Trip,
  type TripForm,
} from "./postTrip";

const NOW = new Date("2026-10-15T20:00:00"); // local time, so this passes in any time zone
const OSBORNE: [number, number] = [-97.1438, 49.8768];

const form = (changes: Partial<TripForm> = {}): TripForm => ({
  direction: "to_campus",
  point: OSBORNE,
  date: "2026-10-16",
  time: "07:45",
  seats: 3,
  ...changes,
});

describe("buildPostTrip", () => {
  it("builds the contract's request, with the area's name as the label", () => {
    expect(buildPostTrip(form(), NOW)).toEqual({
      body: {
        direction: "to_campus",
        place: { label: "Osborne Village area", lat: 49.8768, lng: -97.1438 },
        departureAt: toSearchTime("2026-10-16", "07:45"),
        seatsTotal: 3,
      },
    });
  });

  it("asks for a place first", () => {
    expect(buildPostTrip(form({ point: undefined }), NOW)).toEqual({
      problem: { field: "place", message: "Tap the map or use your location to choose where you start." },
    });
  });

  it("refuses places outside Winnipeg", () => {
    const result = buildPostTrip(form({ point: [-96.0, 50.5] }), NOW);
    expect("problem" in result && result.problem.field).toBe("place");
  });

  it("refuses a departure in the past, or a missing one", () => {
    expect(buildPostTrip(form({ date: "2026-10-15", time: "19:00" }), NOW)).toEqual({
      problem: { field: "departure", message: "Choose a departure time in the future." },
    });
    const missing = buildPostTrip(form({ time: "" }), NOW);
    expect("problem" in missing && missing.problem.field).toBe("departure");
  });

  it("only allows 1 to 6 seats, as the contract does", () => {
    for (const seats of [0, 7]) {
      const result = buildPostTrip(form({ seats }), NOW);
      expect("problem" in result && result.problem.field).toBe("seats");
    }
    expect("body" in buildPostTrip(form({ seats: 6 }), NOW)).toBe(true);
  });
});

describe("placeLabel", () => {
  it("names the neighbourhood, never an address", () => {
    expect(placeLabel(OSBORNE)).toBe("Osborne Village area");
    expect(placeLabel([-97.4, 49.7])).toBe("Your chosen spot");
  });
});

describe("defaultDeparture", () => {
  it("is tomorrow, early for campus and late afternoon from it", () => {
    expect(defaultDeparture("to_campus", NOW)).toEqual({ date: "2026-10-16", time: "07:45" });
    expect(defaultDeparture("from_campus", NOW)).toEqual({ date: "2026-10-16", time: "16:45" });
  });
});

describe("formatting", () => {
  it("shows durations in minutes, then hours", () => {
    expect(formatDuration(1320)).toBe("22 min");
    expect(formatDuration(20)).toBe("1 min");
    expect(formatDuration(3600)).toBe("1 h");
    expect(formatDuration(3900)).toBe("1 h 5 min");
  });

  it("shows distances in km", () => {
    expect(formatDistance(14_200)).toBe("14 km");
    expect(formatDistance(9_340)).toBe("9.3 km");
  });

  it("shows clock times", () => {
    expect(formatClock(new Date("2026-10-16T07:35:00").toISOString())).toBe("7:35 AM");
    expect(formatClock(new Date("2026-10-16T16:05:00").toISOString())).toBe("4:05 PM");
  });
});

describe("findOverlap", () => {
  const at = (time: string) => new Date(`2026-10-16T${time}`).toISOString();
  const trip = (departs: string, arrives: string, status: Trip["status"] = "scheduled"): Trip => ({
    id: `${departs}-${status}`,
    driverId: "me",
    direction: "to_campus",
    origin: { label: "Osborne Village area", lat: 49.8768, lng: -97.1438 },
    destination: { label: "University Centre", lat: 49.8075, lng: -97.1366 },
    departureAt: at(departs),
    estimatedArrivalAt: at(arrives),
    durationSeconds: 1320,
    distanceMeters: 14_000,
    seatsTotal: 3,
    seatsAvailable: 3,
    status,
  });
  const morning = trip("07:30", "07:52");

  it("finds a trip the new departure falls in", () => {
    expect(findOverlap([morning], at("07:45"))).toBe(morning);
    expect(findOverlap([morning], at("07:30"))).toBe(morning);
  });

  it("needs 30 minutes before another trip leaves", () => {
    expect(findOverlap([morning], at("07:05"))).toBe(morning);
    expect(findOverlap([morning], at("07:00"))).toBeUndefined();
  });

  it("allows leaving once the other trip has arrived", () => {
    expect(findOverlap([morning], at("07:52"))).toBeUndefined();
    expect(findOverlap([morning], at("16:45"))).toBeUndefined();
  });

  it("ignores cancelled and completed trips", () => {
    expect(findOverlap([trip("07:30", "07:52", "cancelled"), trip("07:30", "07:52", "completed")], at("07:45"))).toBeUndefined();
  });

  it("names the clashing trip", () => {
    expect(overlapMessage(morning)).toBe("You already have a trip at 7:30 AM on Fri, Oct 16. Choose a different time.");
  });
});
